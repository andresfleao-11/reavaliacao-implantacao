# Configuração dos Serviços no Railway

Este projeto requer os seguintes serviços no Railway:

## Serviços Necessários

| Serviço | Root Directory | Start Command |
|---------|----------------|---------------|
| **postgres** | - | (Plugin Railway) |
| **redis** | - | (Plugin Railway) |
| **backend** | `backend` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **celery-worker** | `backend` | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=6` |
| **celery-beat** | `backend` | `celery -A app.tasks.celery_app beat --loglevel=info` |
| **frontend** | `frontend` | `npm start` |

## 1. Plugins (Postgres e Redis)

No painel do Railway:
1. Clique em **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Clique em **"+ New"** → **"Database"** → **"Redis"**

## 2. Backend API

1. **"+ New"** → **"GitHub Repo"** → Selecione o repositório
2. **Settings**:
   - Service Name: `backend`
   - Root Directory: `backend`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Variables**:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   ANTHROPIC_API_KEY=<sua-chave>
   SERPAPI_KEY=<sua-chave>
   STORAGE_PATH=/app/data
   SEARCH_PROVIDER=serpapi
   ANTHROPIC_MODEL=claude-sonnet-4-20250514
   SERPAPI_ENGINE=google_shopping
   ```

## 3. Celery Worker

1. **"+ New"** → **"GitHub Repo"** → Selecione o repositório
2. **Settings**:
   - Service Name: `celery-worker`
   - Root Directory: `backend`
   - Start Command: `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=6 --prefetch-multiplier=1`
3. **Variables**: (mesmas do backend)

## 4. Celery Beat (Agendador)

1. **"+ New"** → **"GitHub Repo"** → Selecione o repositório
2. **Settings**:
   - Service Name: `celery-beat`
   - Root Directory: `backend`
   - Start Command: `celery -A app.tasks.celery_app beat --loglevel=info`
3. **Variables**:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   REDIS_URL=${{Redis.REDIS_URL}}
   ```

### Tasks Agendadas pelo Beat

| Task | Frequência | Descrição |
|------|------------|-----------|
| `update_exchange_rate` | Diário 23:00 | Atualiza taxa USD→BRL do BCB |
| `recover_stuck_quotes` | A cada 5 min | Recupera cotações travadas |
| `fix_stuck_batches` | A cada 10 min | Corrige lotes com status incorreto |
| `cleanup_old_processing` | Diário 04:00 | Limpa cotações antigas em PROCESSING |
| `sync_inventory_master_data` | Diário 02:00 | Sincroniza dados do ASI |
| `check_inventory_sessions_status` | A cada hora | Verifica sessões de inventário |

## 5. Frontend

1. **"+ New"** → **"GitHub Repo"** → Selecione o repositório
2. **Settings**:
   - Service Name: `frontend`
   - Root Directory: `frontend`
   - Start Command: `npm start`
3. **Variables**:
   ```
   NEXT_PUBLIC_API_URL=https://<backend-url>.up.railway.app
   ```

## Variáveis Compartilhadas

Para facilitar, você pode usar referências entre serviços:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

## Verificação

Após o deploy, verifique:

1. **Backend**: Acesse `https://<backend>/docs` - deve mostrar Swagger UI
2. **Celery Worker**: Logs devem mostrar "celery@... ready"
3. **Celery Beat**: Logs devem mostrar "beat: Starting..."
4. **Frontend**: Acesse a URL e faça login

## Troubleshooting

### Celery Beat não executa tasks
- Verifique se `REDIS_URL` está configurado
- Verifique logs: deve mostrar "Scheduler: Sending due task..."

### Taxa de câmbio não atualiza
- A task `update_exchange_rate` roda às 23:00
- Para testar manualmente, chame o endpoint `/api/settings/update-exchange-rate`
