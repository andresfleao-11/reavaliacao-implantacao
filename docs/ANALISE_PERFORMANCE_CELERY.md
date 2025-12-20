# Analise de Performance - Sistema de Cotacoes

**Data:** 20/12/2024
**Versao:** 1.0
**Autor:** Claude Code

---

## Indice

1. [Resumo Executivo](#1-resumo-executivo)
2. [Arquitetura do Sistema de Filas](#2-arquitetura-do-sistema-de-filas)
3. [Fluxo de Processamento](#3-fluxo-de-processamento)
4. [Configuracao Atual](#4-configuracao-atual)
5. [Analise de Gargalos](#5-analise-de-gargalos)
6. [Simulacao de Carga](#6-simulacao-de-carga)
7. [Impacto do Numero de Workers](#7-impacto-do-numero-de-workers)
8. [Limites do Sistema](#8-limites-do-sistema)
9. [Melhorias Implementadas](#9-melhorias-implementadas)
10. [Configuracao Recomendada](#10-configuracao-recomendada)
11. [Monitoramento](#11-monitoramento)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Resumo Executivo

### O que e este documento?

Analise completa do sistema de processamento de cotacoes em lote, incluindo:
- Como as cotacoes sao processadas (fila, paralelismo)
- Limites de capacidade
- Gargalos identificados
- Melhorias implementadas
- Recomendacoes de configuracao

### Principais Conclusoes

| Metrica | Valor Atual | Otimizado |
|---------|-------------|-----------|
| Workers | 6 | 6-8 |
| Rate Limit | 3/s | 3-4/s |
| Capacidade | ~10.800/hora | ~14.400/hora |
| Tempo 100k cotacoes | ~9 horas | ~7 horas |

---

## 2. Arquitetura do Sistema de Filas

### Componentes

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Redis    │────▶│   Celery    │
│  (Backend)  │     │   (Broker)  │     │  (Workers)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                                       │
       │                                       │
       ▼                                       ▼
┌─────────────┐                         ┌─────────────┐
│ PostgreSQL  │◀────────────────────────│    APIs     │
│    (DB)     │                         │  Externas   │
└─────────────┘                         └─────────────┘
```

### Tecnologias

| Componente | Tecnologia | Funcao |
|------------|------------|--------|
| Backend | FastAPI | API REST, criacao de cotacoes |
| Broker | Redis | Fila de mensagens |
| Worker | Celery | Processamento assincrono |
| Database | PostgreSQL | Persistencia de dados |
| APIs | Anthropic, SerpAPI | IA e busca de precos |

---

## 3. Fluxo de Processamento

### 3.1 Cotacao Individual

```
Usuario cria cotacao
        │
        ▼
┌───────────────────┐
│ API cria registro │  ← Sincrono (instantaneo)
│ status=PROCESSING │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Task entra na     │  ← Assincrono
│ fila Redis        │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Worker disponivel │
│ pega a task       │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 1. Analise IA     │  ~5-10s
│ 2. Busca Shopping │  ~5-10s
│ 3. Extracao preco │  ~10-20s
│ 4. Finalizacao    │  ~2-5s
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ status=DONE       │
│ Resultado salvo   │
└───────────────────┘
```

### 3.2 Cotacao em Lote

```
Usuario cria lote (N cotacoes)
        │
        ▼
┌───────────────────────────────────────┐
│ API cria:                             │
│ - 1 registro BatchQuoteJob            │
│ - N registros QuoteRequest            │
│ - Dispara process_batch_job           │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ process_batch_job:                    │
│ - Para cada cotacao, dispara          │
│   process_batch_quote na fila         │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ FILA REDIS                            │
│ [Q1] [Q2] [Q3] [Q4] [Q5] ... [QN]     │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ POOL DE WORKERS (6 workers)           │
│                                       │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ │
│ │ W1 │ │ W2 │ │ W3 │ │ W4 │ │ W5 │ │ W6 │ │
│ │ Q1 │ │ Q2 │ │ Q3 │ │ Q4 │ │ Q5 │ │ Q6 │ │
│ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ │
│                                       │
│ Quando W1 termina Q1, pega Q7         │
│ Quando W2 termina Q2, pega Q8         │
│ ... e assim por diante                │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ Cada worker ao terminar:              │
│ - Atualiza status da cotacao          │
│ - Chama _update_batch_on_quote_complete│
│ - Verifica se lote terminou           │
└───────────────────────────────────────┘
```

---

## 4. Configuracao Atual

### 4.1 Celery App (celery_app.py)

```python
celery_app.conf.update(
    # Serializacao
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,

    # Performance
    worker_prefetch_multiplier=1,  # 1 task por vez por worker
    task_acks_late=True,           # Confirma apos processar
    task_reject_on_worker_lost=True,

    # Rate Limiting
    task_annotations={
        'process_quote_request': {'rate_limit': '3/s'},
        'process_batch_quote': {'rate_limit': '3/s'},
    },

    # Timeout
    task_time_limit=600,      # 10 minutos maximo
    task_soft_time_limit=540, # Aviso aos 9 minutos
)
```

### 4.2 Docker Compose (celery-worker)

```yaml
celery-worker:
  command: celery -A app.tasks.celery_app worker
           --loglevel=info
           --concurrency=6
           --prefetch-multiplier=1
```

### 4.3 Parametros Explicados

| Parametro | Valor | Significado |
|-----------|-------|-------------|
| `--concurrency=6` | 6 | Numero de processos paralelos |
| `--prefetch-multiplier=1` | 1 | Cada worker pega 1 task por vez |
| `rate_limit='3/s'` | 3/s | Maximo 3 tasks iniciam por segundo |
| `task_time_limit=600` | 600s | Task morre apos 10 minutos |
| `task_acks_late=True` | True | Confirma task apos completar |

---

## 5. Analise de Gargalos

### 5.1 Hierarquia de Gargalos

```
NIVEL 1: Rate Limit das APIs Externas
         ├── Anthropic: ~50-100 req/min
         └── SerpAPI: ~100 req/min
              │
              ▼
NIVEL 2: Rate Limit do Celery (3/s = 180/min)
              │
              ▼
NIVEL 3: Numero de Workers (6)
              │
              ▼
NIVEL 4: Recursos de Hardware (CPU/RAM)
```

### 5.2 Identificacao de Gargalos

| Gargalo | Tipo | Impacto | Solucao |
|---------|------|---------|---------|
| Rate Limit Celery | Configuravel | Alto | Aumentar se APIs suportarem |
| APIs Externas | Fixo (plano) | Alto | Upgrade de plano |
| Workers | Configuravel | Medio | Aumentar com cautela |
| RAM | Hardware | Medio | Escalar verticalmente |
| Conexoes DB | Configuravel | Baixo | Connection pooling |

### 5.3 Gargalo Principal: Rate Limit

```
COM rate_limit='3/s':

Segundo 1: [Task1] [Task2] [Task3] ░░░░░░  ← 3 tasks iniciam
Segundo 2: [Task4] [Task5] [Task6] ░░░░░░  ← 3 tasks iniciam
Segundo 3: [Task7] [Task8] [Task9] ░░░░░░  ← 3 tasks iniciam

Workers disponiveis: 6
Tasks iniciadas/segundo: 3 (limitado pelo rate limit)
Workers ociosos: 3 (50% do tempo)

Throughput: 3/s × 3600s = 10.800/hora
```

---

## 6. Simulacao de Carga

### 6.1 Lote de 100 Cotacoes

| Metrica | Valor |
|---------|-------|
| Tempo de criacao | ~2-5 segundos |
| Tempo de processamento | ~35-40 segundos |
| Workers ativos | 6 |
| Taxa efetiva | ~3/segundo |

### 6.2 Lote de 1.000 Cotacoes

| Metrica | Valor |
|---------|-------|
| Tempo de criacao | ~10-20 segundos |
| Tempo de processamento | ~5-6 minutos |
| Workers ativos | 6 |
| Taxa efetiva | ~3/segundo |

### 6.3 Lote de 10.000 Cotacoes

| Metrica | Valor |
|---------|-------|
| Tempo de criacao | ~1-2 minutos |
| Tempo de processamento | ~55-60 minutos |
| Workers ativos | 6 |
| Taxa efetiva | ~3/segundo |

### 6.4 Lote de 100.000 Cotacoes

| Metrica | Valor |
|---------|-------|
| Tempo de criacao | ~5-10 minutos |
| Tempo de processamento | ~9-10 horas |
| Workers ativos | 6 |
| Taxa efetiva | ~3/segundo |
| Custo APIs estimado | $3.000 - $7.000 |

### 6.5 Timeline Visual (100k)

```
HORA 0     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%
HORA 1     ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10.8%
HORA 2     ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  21.6%
HORA 3     ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  32.4%
HORA 4     ████████████████░░░░░░░░░░░░░░░░░░░░░░░░  43.2%
HORA 5     ████████████████████░░░░░░░░░░░░░░░░░░░░  54.0%
HORA 6     ████████████████████████░░░░░░░░░░░░░░░░  64.8%
HORA 7     ████████████████████████████░░░░░░░░░░░░  75.6%
HORA 8     ████████████████████████████████░░░░░░░░  86.4%
HORA 9     ████████████████████████████████████░░░░  97.2%
HORA 9:15  ████████████████████████████████████████  100% ✓
```

---

## 7. Impacto do Numero de Workers

### 7.1 Relacao Workers vs Throughput

```
Throughput │
(por hora) │
           │                    ┌─── Limite: Rate Limit APIs
   14.400 ─┤              ●────●────●
           │          ●
   10.800 ─┤      ●
           │    ●
    7.200 ─┤  ●
           │ ●
    3.600 ─┤●
           │
       0 ──┼──┬──┬──┬──┬──┬──┬──┬──┬──
           0  2  4  6  8  10 12 14 16  Workers

           └────────┘ └────────────────┘
           Ganho real  Retorno decrescente
```

### 7.2 Tabela de Impacto

| Workers | RAM | Conexoes DB | Throughput | Ganho vs Anterior |
|---------|-----|-------------|------------|-------------------|
| 2 | 1 GB | 4 | 7.200/h | - |
| 4 | 2 GB | 8 | 10.800/h | +50% |
| 6 | 3 GB | 12 | 10.800/h | +0% (rate limit) |
| 8 | 4 GB | 16 | 10.800/h | +0% (rate limit) |
| 12 | 6 GB | 24 | 10.800/h | +0% (rate limit) |
| 16 | 8 GB | 32 | 10.800/h | +0% (rate limit) |

### 7.3 Conclusao

> **Aumentar workers alem de 4-6 NAO melhora throughput se o rate limit for 3/s.**
>
> Para ganhar performance, deve-se aumentar AMBOS:
> - Rate limit (se APIs suportarem)
> - Numero de workers (proporcional)

### 7.4 Configuracoes Recomendadas

| Cenario | Workers | Rate Limit | Throughput | Custo |
|---------|---------|------------|------------|-------|
| Economico | 4 | 2/s | 7.200/h | $ |
| **Padrao** | **6** | **3/s** | **10.800/h** | **$$** |
| Otimizado | 8 | 4/s | 14.400/h | $$$ |
| Agressivo | 12 | 6/s | 21.600/h | $$$$ |

---

## 8. Limites do Sistema

### 8.1 Limites de Hardware

| Recurso | Por Worker | 6 Workers | 12 Workers | Limite Tipico |
|---------|------------|-----------|------------|---------------|
| RAM | 500 MB | 3 GB | 6 GB | 8-16 GB |
| CPU | 25% | 150% | 300% | 400% (4 cores) |
| Conexoes DB | 2 | 12 | 24 | 100 |

### 8.2 Limites de APIs

| API | Limite Tipico | Impacto |
|-----|---------------|---------|
| Anthropic | 50-100 req/min | Principal gargalo |
| SerpAPI | 100 req/min | Secundario |
| OpenAI | 60-500 req/min | Se usado |

### 8.3 Limites de Infraestrutura Railway

| Recurso | Plano Hobby | Plano Pro |
|---------|-------------|-----------|
| RAM | 512 MB | 8+ GB |
| CPU | Compartilhado | Dedicado |
| Conexoes DB | 20 | 100+ |

---

## 9. Melhorias Implementadas

### 9.1 Correcao de Race Condition (batch_tasks.py)

**Problema:** Multiplos workers atualizando o mesmo lote simultaneamente causavam contagem incorreta.

**Solucao:** Lock `FOR UPDATE` no banco de dados.

```python
def _update_batch_on_quote_complete(db: Session, batch_job_id: int):
    # Lock no batch para evitar race condition
    batch = db.query(BatchQuoteJob).filter(
        BatchQuoteJob.id == batch_job_id
    ).with_for_update().first()

    # ... resto da logica
```

### 9.2 Task de Auto-Correcao (scheduled_tasks.py)

**Problema:** Lotes podiam ficar travados em PROCESSING mesmo com todas cotacoes finalizadas.

**Solucao:** Task agendada que verifica e corrige a cada 10 minutos.

```python
@celery_app.task(name="fix_stuck_batches")
def fix_stuck_batches():
    """
    Verifica lotes em PROCESSING onde todas as cotacoes ja terminaram
    e atualiza o status corretamente.
    """
    # Executada a cada 10 minutos via Celery Beat
```

### 9.3 Rate Limiting (celery_app.py)

**Problema:** Sem controle, workers podiam sobrecarregar APIs externas.

**Solucao:** Rate limit configuravel por task.

```python
task_annotations={
    'process_quote_request': {'rate_limit': '3/s'},
    'process_batch_quote': {'rate_limit': '3/s'},
},
```

### 9.4 Controle de Concorrencia (docker-compose.yml)

**Problema:** Sem limite, Celery usava todos os CPUs disponiveis.

**Solucao:** Flag `--concurrency` no comando do worker.

```yaml
command: celery -A app.tasks.celery_app worker
         --loglevel=info
         --concurrency=6
         --prefetch-multiplier=1
```

---

## 10. Configuracao Recomendada

### 10.1 Para Ambiente Local/Desenvolvimento

```yaml
# docker-compose.yml
celery-worker:
  command: celery -A app.tasks.celery_app worker
           --loglevel=info
           --concurrency=4
           --prefetch-multiplier=1
```

```python
# celery_app.py
task_annotations={
    'process_quote_request': {'rate_limit': '2/s'},
    'process_batch_quote': {'rate_limit': '2/s'},
},
```

### 10.2 Para Producao (Railway)

```
Start Command do celery-worker:
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=6 --prefetch-multiplier=1
```

```python
# celery_app.py
task_annotations={
    'process_quote_request': {'rate_limit': '3/s'},
    'process_batch_quote': {'rate_limit': '3/s'},
},
```

### 10.3 Para Alta Carga (100k+ cotacoes)

```yaml
# Considerar multiplas instancias de worker
# Ou aumentar concurrency para 8-12
celery-worker:
  command: celery -A app.tasks.celery_app worker
           --loglevel=info
           --concurrency=8
           --prefetch-multiplier=1
```

```python
# celery_app.py - se APIs suportarem
task_annotations={
    'process_quote_request': {'rate_limit': '5/s'},
    'process_batch_quote': {'rate_limit': '5/s'},
},
```

---

## 11. Monitoramento

### 11.1 Verificar Status dos Workers

```bash
# Via Docker
docker exec projeto_reavaliacao-celery-worker-1 \
  celery -A app.tasks.celery_app inspect stats

# Saida esperada:
# "pool": {
#     "max-concurrency": 6,
#     "processes": [pid1, pid2, pid3, pid4, pid5, pid6]
# }
```

### 11.2 Verificar Fila

```bash
# Quantidade de tasks na fila
docker exec projeto_reavaliacao-redis-1 redis-cli LLEN celery
```

### 11.3 Logs do Worker

```bash
# Tempo real
docker logs -f projeto_reavaliacao-celery-worker-1

# Ultimas 100 linhas
docker logs --tail 100 projeto_reavaliacao-celery-worker-1
```

### 11.4 Metricas de Performance

```python
# Via API (se implementado)
GET /api/system/health

# Resposta:
{
    "celery_workers": 6,
    "queue_size": 150,
    "processing_quotes": 6,
    "completed_last_hour": 10800
}
```

---

## 12. Troubleshooting

### 12.1 Lote Fica Travado em PROCESSING

**Sintoma:** Barra de progresso nao atualiza, status = PROCESSING

**Causa:** Race condition ou worker crashou

**Solucao:**
1. Aguardar task `fix_stuck_batches` (roda a cada 10 min)
2. Ou forcar manualmente:
```bash
docker exec projeto_reavaliacao-backend-1 python -c "
from app.tasks.scheduled_tasks import fix_stuck_batches
result = fix_stuck_batches()
print(result)
"
```

### 12.2 Workers Ociosos

**Sintoma:** Poucos workers ativos mesmo com fila cheia

**Causa:** Rate limit muito baixo

**Solucao:** Aumentar rate limit em celery_app.py

### 12.3 Erros 429 (Too Many Requests)

**Sintoma:** Logs mostram erros de rate limit das APIs

**Causa:** Rate limit muito alto

**Solucao:** Diminuir rate limit em celery_app.py

### 12.4 Worker Sem Memoria

**Sintoma:** Worker reinicia frequentemente, OOM killer

**Causa:** Muitos workers para a RAM disponivel

**Solucao:** Reduzir `--concurrency` ou aumentar RAM

### 12.5 Conexoes DB Esgotadas

**Sintoma:** Erros "too many connections"

**Causa:** Muitos workers abrindo conexoes

**Solucao:**
- Reduzir workers
- Implementar connection pooling
- Aumentar limite do PostgreSQL

---

## Apendice A: Comandos Uteis

```bash
# Recriar worker com nova configuracao
docker-compose up -d --force-recreate celery-worker

# Ver configuracao atual do worker
docker exec projeto_reavaliacao-celery-worker-1 \
  celery -A app.tasks.celery_app inspect conf

# Listar tasks registradas
docker exec projeto_reavaliacao-celery-worker-1 \
  celery -A app.tasks.celery_app inspect registered

# Purgar fila (CUIDADO: remove todas as tasks)
docker exec projeto_reavaliacao-celery-worker-1 \
  celery -A app.tasks.celery_app purge -f
```

---

## Apendice B: Formulas

```
Throughput (tasks/hora) = min(rate_limit × 3600, workers × tasks_por_worker_hora)

Tempo para N cotacoes = N / Throughput

RAM necessaria = workers × 500MB (aproximado)

Conexoes DB = workers × 2
```

---

## Historico de Alteracoes

| Data | Versao | Alteracao |
|------|--------|-----------|
| 20/12/2024 | 1.0 | Versao inicial |

---

*Documento gerado automaticamente por Claude Code*
