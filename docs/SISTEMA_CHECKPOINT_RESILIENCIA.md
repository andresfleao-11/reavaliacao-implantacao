# Sistema de Checkpoints e Resiliência para Cotações

## Visão Geral

Este documento descreve o sistema de checkpoints implementado para garantir a resiliência do processamento de cotações, permitindo retomada automática após falhas, atualizações ou interrupções de serviço.

## Problema Resolvido

Antes desta implementação, quando o sistema era interrompido (deploy, erro, crash), as cotações em processamento ficavam "travadas" com status `PROCESSING` indefinidamente, sem possibilidade de retomada automática.

### Cenários Cobertos

1. **Deploy/Atualização**: Containers reiniciados durante processamento
2. **Crash do Worker**: Celery worker morre inesperadamente
3. **Timeout de Conexão**: Perda de conexão com APIs externas
4. **Erro de Memória**: Worker excede limite de memória
5. **Interrupção Manual**: Administrador para o serviço

## Arquitetura da Solução

### 1. Campos de Checkpoint (QuoteRequest)

```python
# Novos campos adicionados ao modelo
processing_checkpoint = Column(String(50))  # Etapa atual
last_heartbeat = Column(DateTime)           # Último sinal de vida
worker_id = Column(String(100))             # ID do worker processando
resume_data = Column(JSON)                  # Dados para retomada
started_at = Column(DateTime)               # Início do processamento
completed_at = Column(DateTime)             # Fim do processamento
```

### 2. Checkpoints Definidos

O processamento de uma cotação passa pelos seguintes checkpoints:

```
INIT
  ↓
AI_ANALYSIS_START → AI_ANALYSIS_DONE
  ↓
FIPE_SEARCH (veículos) OU SHOPPING_SEARCH_START
  ↓
SHOPPING_SEARCH_DONE
  ↓
PRICE_EXTRACTION_START → PRICE_EXTRACTION_PROGRESS → PRICE_EXTRACTION_DONE
  ↓
FINALIZATION
  ↓
COMPLETED
```

### 3. Detecção de Cotações Travadas

Uma cotação é considerada "travada" quando:
- Status = `PROCESSING`
- `last_heartbeat` > 10 minutos atrás

### 4. Tasks Agendadas

| Task | Frequência | Função |
|------|-----------|--------|
| `recover_stuck_quotes` | A cada 5 min | Detecta e re-enfileira cotações travadas |
| `cleanup_old_processing` | Diariamente 04:00 | Marca cotações > 24h como ERROR |

## API de Monitoramento

### Endpoints Disponíveis

```
GET  /api/system/health              - Health check básico
GET  /api/system/processing-stats    - Estatísticas de processamento
GET  /api/system/stuck-quotes        - Lista cotações travadas
POST /api/system/recover-stuck       - Dispara recuperação manual
POST /api/system/recover-quote/{id}  - Recupera cotação específica
POST /api/system/resume-batch/{id}   - Retoma lote interrompido
GET  /api/system/batch-status/{id}   - Status detalhado do lote
POST /api/system/cleanup-old         - Limpeza manual
```

### Exemplo de Resposta - Processing Stats

```json
{
  "total_processing": 150,
  "stuck_count": 3,
  "by_checkpoint": {
    "PRICE_EXTRACTION_PROGRESS": 120,
    "SHOPPING_SEARCH_DONE": 25,
    "AI_ANALYSIS_DONE": 5
  },
  "avg_processing_time_seconds": 45.32
}
```

## Fluxo de Recuperação

```
┌─────────────────────────────────────────────────────────────────┐
│                    CELERY BEAT (a cada 5 min)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Buscar cotações com status=PROCESSING e heartbeat > 10min  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Para cada cotação travada:                                  │
│     - Limpar worker_id                                          │
│     - Incrementar attempt_number                                │
│     - Enfileirar process_quote_request.delay(id)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Worker pega a task e verifica checkpoint:                   │
│     - Se tem claude_payload_json → Pula AI_ANALYSIS             │
│     - Se tem google_shopping_response_json → Pula SHOPPING      │
│     - Se tem resume_data.tested_products → Continua extração    │
└─────────────────────────────────────────────────────────────────┘
```

## Decisões de Design

### 1. Por que Heartbeat ao invés de Lock Distribuído?

**Escolha**: Heartbeat com timeout de 10 minutos

**Justificativa**:
- Simplicidade: Não requer infraestrutura adicional (Redis locks, Consul, etc.)
- Robustez: Funciona mesmo se o worker morrer sem liberar lock
- Escalabilidade: Cada worker atualiza apenas seus próprios heartbeats

**Trade-off**: Pode haver breve período de "falso positivo" se worker estiver lento mas vivo.

### 2. Por que 10 minutos de timeout?

**Justificativa**:
- Etapa mais longa (price_extraction) pode levar até 5 minutos
- Buffer de segurança de 2x
- Evita recuperação prematura de cotações que ainda estão sendo processadas

### 3. Por que salvar checkpoint a cada etapa?

**Justificativa**:
- Minimiza reprocessamento em caso de falha
- Chamadas de API (Anthropic, SerpAPI) são caras
- Permite análise de onde o sistema mais falha

### 4. Por que usar JSON para resume_data?

**Justificativa**:
- Flexibilidade para diferentes tipos de dados
- Permite adicionar novos campos sem migração
- Fácil debug e inspeção

### 5. Por que task a cada 5 minutos?

**Justificativa**:
- Suficiente para recuperar rapidamente após falha
- Não sobrecarrega o sistema com verificações constantes
- Timeout de 10 min = 2 ciclos de verificação antes de recuperar

## Índices de Banco de Dados

```sql
-- Para buscar cotações travadas rapidamente
CREATE INDEX ix_quote_requests_heartbeat_status
ON quote_requests (status, last_heartbeat);

-- Para identificar workers ativos
CREATE INDEX ix_quote_requests_worker_id
ON quote_requests (worker_id);
```

## Escalabilidade para 10.000 Cotações

### Gargalos Identificados

1. **APIs Externas**: Rate limits do SerpAPI e Anthropic
2. **Database**: Pool de conexões e locks
3. **Workers**: Concorrência de Celery
4. **Storage**: I/O de screenshots

### Recomendações para Alta Escala

```yaml
# docker-compose.yml - Exemplo para produção
celery-worker:
  command: celery -A app.tasks.celery_app worker
           --loglevel=info
           --concurrency=20
           --pool=prefork
  deploy:
    replicas: 5
    resources:
      limits:
        memory: 2G
```

### Configurações Recomendadas

| Configuração | Valor para 10k | Justificativa |
|--------------|---------------|---------------|
| Workers | 5 réplicas | Distribuição de carga |
| Concurrency | 20 por worker | 100 tasks simultâneas |
| DB Pool | 50 conexões | Suportar workers paralelos |
| Redis Connections | 100 | Broker + Result Backend |
| Heartbeat Timeout | 10 min | Suficiente para tasks longas |

## Uso do CheckpointManager

### Integração no quote_tasks.py

```python
from app.services.checkpoint_manager import CheckpointManager, ProcessingCheckpoint

def process_quote_request(quote_request_id: int):
    db = SessionLocal()
    quote = db.query(QuoteRequest).get(quote_request_id)

    checkpoint_mgr = CheckpointManager(db)

    # Verificar se pode retomar
    if checkpoint_mgr.can_resume(quote):
        resume_from = checkpoint_mgr.get_resume_checkpoint(quote)
        # Pular para o checkpoint apropriado
    else:
        checkpoint_mgr.start_processing(quote)

    # Salvar checkpoint após AI analysis
    checkpoint_mgr.save_checkpoint(
        quote,
        ProcessingCheckpoint.AI_ANALYSIS_DONE,
        progress_percentage=30
    )

    # Durante processamento longo, atualizar heartbeat
    for product in products:
        checkpoint_mgr.update_heartbeat(quote)
        # ... processar produto ...

    # Finalizar
    checkpoint_mgr.complete_processing(quote, QuoteStatus.DONE)
```

## Monitoramento

### Métricas Importantes

1. **stuck_count**: Deve ser próximo de 0
2. **avg_processing_time**: Baseline ~45s, alertar se > 120s
3. **by_checkpoint**: Identificar gargalos

### Alertas Sugeridos

```yaml
# Prometheus/Grafana
alerts:
  - name: HighStuckQuotes
    condition: stuck_count > 10
    severity: warning

  - name: SlowProcessing
    condition: avg_processing_time > 120
    severity: warning

  - name: WorkerHealthCheck
    condition: no heartbeat updates in 15 min
    severity: critical
```

## Migração

### Aplicar Migração

```bash
# Local
docker exec -it projeto_reavaliacao-backend-1 alembic upgrade head

# Railway
# Automaticamente aplicado no deploy
```

### Rollback (se necessário)

```bash
alembic downgrade 028
```

## Conclusão

O sistema de checkpoints fornece:

1. **Resiliência**: Cotações não se perdem após falhas
2. **Eficiência**: Retomada do ponto onde parou
3. **Visibilidade**: Estatísticas e monitoramento
4. **Recuperação Manual**: Endpoints para intervenção

A implementação foi projetada para ser não-intrusiva, podendo ser integrada gradualmente ao código existente de `quote_tasks.py`.
