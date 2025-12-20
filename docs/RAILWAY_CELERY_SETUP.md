# Configuração do Celery no Railway

Este guia explica como configurar o Celery Worker e Celery Beat no Railway.

## Arquitetura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Backend   │     │   Celery    │     │   Celery    │
│   (API)     │────▶│   Worker    │◀────│    Beat     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────▼──────┐
                    │    Redis    │
                    └─────────────┘
```

- **Backend**: API FastAPI que enfileira tasks
- **Celery Worker**: Executa as tasks da fila
- **Celery Beat**: Agendador que dispara tasks periódicas
- **Redis**: Broker de mensagens entre os serviços

---

## 1. Criar Celery Worker

### Passo 1: Novo Serviço
- No Railway, clique **"+ New"** → **"GitHub Repo"**
- Selecione: `reavaliacao-implantacao`

### Passo 2: Configurar Build
Vá em **Settings** → **Build**:

| Campo | Valor |
|-------|-------|
| Builder | `Nixpacks` |
| Root Directory | `backend` |

### Passo 3: Configurar Deploy
Vá em **Settings** → **Deploy**:

| Campo | Valor |
|-------|-------|
| Start Command | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4` |

### Passo 4: Variáveis de Ambiente
Vá em **Variables** e adicione:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ANTHROPIC_API_KEY=<sua-chave-anthropic>
SERPAPI_KEY=<sua-chave-serpapi>
STORAGE_PATH=/app/data
SEARCH_PROVIDER=serpapi
ANTHROPIC_MODEL=claude-sonnet-4-20250514
SERPAPI_ENGINE=google_shopping
```

### Passo 5: Deploy
Clique em **Deploy** e aguarde.

### Verificação
Nos logs deve aparecer:
```
celery@... ready.
Connected to redis://...
```

---

## 2. Criar Celery Beat

### Passo 1: Novo Serviço
- No Railway, clique **"+ New"** → **"GitHub Repo"**
- Selecione: `reavaliacao-implantacao`

### Passo 2: Configurar Build
Vá em **Settings** → **Build**:

| Campo | Valor |
|-------|-------|
| Builder | `Nixpacks` |
| Root Directory | `backend` |

### Passo 3: Configurar Deploy
Vá em **Settings** → **Deploy**:

| Campo | Valor |
|-------|-------|
| Start Command | `celery -A app.tasks.celery_app beat --loglevel=info` |

### Passo 4: Variáveis de Ambiente
Vá em **Variables** e adicione:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

> **Nota**: O Beat não precisa de ANTHROPIC_API_KEY ou SERPAPI_KEY, pois ele apenas agenda as tasks - quem executa é o Worker.

### Passo 5: Deploy
Clique em **Deploy** e aguarde.

### Verificação
Nos logs deve aparecer:
```
beat: Starting...
Scheduler: Sending due task recover-stuck-quotes (recover_stuck_quotes)
```

---

## 3. Tasks Agendadas

O Celery Beat executa automaticamente:

| Task | Frequência | Descrição |
|------|------------|-----------|
| `recover_stuck_quotes` | A cada 5 min | Recupera cotações travadas |
| `fix_stuck_batches` | A cada 10 min | Corrige lotes com status incorreto |
| `update_exchange_rate` | Diário às 23:00 | Atualiza taxa USD→BRL do BCB |
| `cleanup_old_processing` | Diário às 04:00 | Limpa cotações antigas |
| `sync_inventory_master_data` | Diário às 02:00 | Sincroniza dados do ASI |
| `check_inventory_sessions_status` | A cada hora | Verifica sessões de inventário |

---

## 4. Troubleshooting

### Task não executa
1. Verifique se Worker está rodando (logs mostram "ready")
2. Verifique se Beat está rodando (logs mostram "Starting...")
3. Verifique se ambos usam o mesmo `REDIS_URL`

### Erro de conexão Redis
```
Error connecting to redis://...
```
- Verifique se a variável `REDIS_URL` está configurada
- Use `${{Redis.REDIS_URL}}` para referenciar o Redis do Railway

### Worker não processa
```
Task received but not executed
```
- Verifique se as dependências estão instaladas (requirements.txt)
- Verifique se `ANTHROPIC_API_KEY` e `SERPAPI_KEY` estão configuradas

---

## 5. Comandos Úteis

### Testar conexão Redis (local)
```bash
docker exec projeto_reavaliacao-backend-1 python -c "
from app.tasks.celery_app import celery_app
print(celery_app.control.ping())
"
```

### Disparar task manualmente (local)
```bash
docker exec projeto_reavaliacao-backend-1 python -c "
from app.tasks.scheduled_tasks import update_exchange_rate
result = update_exchange_rate.delay()
print(f'Task ID: {result.id}')
print(f'Result: {result.get(timeout=30)}')
"
```

### Ver tasks registradas
```bash
docker exec projeto_reavaliacao-celery-worker-1 celery -A app.tasks.celery_app inspect registered
```

---

## 6. Resumo dos Serviços Railway

| Serviço | Root Dir | Start Command |
|---------|----------|---------------|
| backend | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| celery-worker | `backend` | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4` |
| celery-beat | `backend` | `celery -A app.tasks.celery_app beat --loglevel=info` |
| frontend | `frontend` | `npm start` |
