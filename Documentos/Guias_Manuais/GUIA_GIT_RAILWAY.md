# Guia Completo: Git + Deploy Railway

Este guia cobre todo o processo desde a inicialização do Git até o deploy no Railway.

---

## PARTE 1: Inicialização do Git

### 1.1 Instalar Git (se não tiver)

**Windows:**
- Download: https://git-scm.com/download/win
- Executar instalador

**Verificar instalação:**
```bash
git --version
```

### 1.2 Configurar Git (primeira vez)

```bash
git config --global user.name "Seu Nome"
git config --global user.email "seu.email@example.com"
```

### 1.3 Inicializar repositório Git

```bash
# Ir para o diretório do projeto
cd C:\Projeto_reavaliacao

# Inicializar Git
git init
```

### 1.4 Verificar .gitignore

O arquivo `.gitignore` já existe. Verifique se contém:

```gitignore
# Python
__pycache__/
*.py[cod]
*.so
venv/
env/

# Environment
.env
.env.local

# Database
*.db
*.sqlite

# Node
node_modules/
.next/

# Data
data/uploads/*
data/screenshots/*
data/pdfs/*

# Docker
*.log

# Temporary
test.db
```

**IMPORTANTE:** Verificar se `.env` está no .gitignore!

### 1.5 Fazer primeiro commit

```bash
# Adicionar todos os arquivos
git add .

# Fazer commit inicial
git commit -m "Initial commit: Sistema de Cotação de Preços MVP"
```

---

## PARTE 2: Criar Repositório no GitHub/GitLab

### 2.1 Criar repositório no GitHub

1. Acessar: https://github.com
2. Clicar em "New repository"
3. Nome: `sistema-cotacao-precos` (ou nome de sua escolha)
4. **NÃO** marcar "Initialize with README"
5. Clicar em "Create repository"

### 2.2 Conectar repositório local ao remoto

```bash
# Adicionar origin (substituir URL pelo seu repositório)
git remote add origin https://github.com/SEU_USUARIO/sistema-cotacao-precos.git

# Verificar
git remote -v

# Push inicial
git branch -M main
git push -u origin main
```

---

## PARTE 3: Rotina de Trabalho Diária

### 3.1 Verificar status

```bash
# Ver arquivos modificados
git status
```

### 3.2 Adicionar mudanças

```bash
# Adicionar arquivos específicos
git add arquivo1.py arquivo2.py

# OU adicionar todos os arquivos modificados
git add .

# OU adicionar por tipo
git add backend/*.py
git add frontend/app/*.tsx
```

### 3.3 Fazer commit

```bash
# Commit com mensagem descritiva
git commit -m "feat: adicionar autenticação JWT"

# OU commit com mensagem detalhada
git commit -m "feat: adicionar autenticação JWT

- Implementar middleware de autenticação
- Adicionar validação de token
- Proteger rotas sensíveis"
```

**Convenções de commit (recomendado):**
- `feat:` - Nova funcionalidade
- `fix:` - Correção de bug
- `docs:` - Documentação
- `style:` - Formatação
- `refactor:` - Refatoração
- `test:` - Testes
- `chore:` - Manutenção

### 3.4 Enviar para GitHub

```bash
git push origin main
```

### 3.5 Fluxo Completo (resumo)

```bash
# 1. Fazer alterações nos arquivos
# 2. Verificar o que mudou
git status
git diff

# 3. Adicionar mudanças
git add .

# 4. Commit
git commit -m "feat: descrição da mudança"

# 5. Push para GitHub
git push origin main
```

---

## PARTE 4: Deploy no Railway

### 4.1 Criar conta no Railway

1. Acessar: https://railway.app
2. Clicar em "Login with GitHub"
3. Autorizar Railway a acessar seus repositórios

### 4.2 Criar novo projeto

1. No dashboard do Railway, clicar em "New Project"
2. Selecionar "Deploy from GitHub repo"
3. Escolher o repositório `sistema-cotacao-precos`
4. Railway detectará automaticamente o Docker Compose

### 4.3 Configurar Variáveis de Ambiente

No Railway, ir em cada serviço e adicionar variáveis:

#### PostgreSQL (Railway cria automaticamente)
Railway cria automaticamente um PostgreSQL. Obter a URL de conexão:

1. Clicar no serviço PostgreSQL
2. Ir em "Variables"
3. Copiar `DATABASE_URL`

#### Backend Service

Adicionar variáveis:
```
DATABASE_URL=postgresql://... (URL do PostgreSQL criado)
REDIS_URL=redis://... (URL do Redis criado)
SERPAPI_API_KEY=SUA_CHAVE_AQUISUA_CHAVE_AQUI
ANTHROPIC_API_KEY=SUA_CHAVE_AQUISUA_CHAVE_AQUI
SECRET_KEY=SUA_CHAVE_AQUI
STORAGE_PATH=/data
SEARCH_PROVIDER=serpapi
SERPAPI_ENGINE=google_shopping
```

#### Frontend Service

Adicionar variáveis:
```
NEXT_PUBLIC_API_URL=https://SEU_BACKEND.railway.app
```

### 4.4 Configurar Dockerfile para Railway

Railway espera um Dockerfile por serviço. Atualizar `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código
COPY . .

# Criar diretórios de dados
RUN mkdir -p /data/uploads /data/screenshots /data/pdfs

# Expor porta
EXPOSE 8000

# Comando de inicialização
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

Atualizar `frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependências
RUN npm ci

# Copiar código
COPY . .

# Build
RUN npm run build

# Expor porta
EXPOSE 3000

# Comando de inicialização
CMD ["npm", "start"]
```

### 4.5 Configurar Serviços no Railway

Railway precisa saber qual Dockerfile usar:

1. **Backend:**
   - Root Directory: `/backend`
   - Build Command: (auto)
   - Start Command: (auto do Dockerfile)

2. **Frontend:**
   - Root Directory: `/frontend`
   - Build Command: (auto)
   - Start Command: (auto do Dockerfile)

3. **Celery Worker:**
   - Root Directory: `/backend`
   - Start Command: `celery -A app.tasks.celery_app worker --loglevel=info`

### 4.6 Executar Migrations

Após deploy do backend:

1. Clicar no serviço Backend
2. Ir em "Deployments"
3. Clicar nos 3 pontos > "View Logs"
4. Verificar se migrations rodaram automaticamente

Se precisar rodar manualmente:
```bash
railway run alembic upgrade head
```

### 4.7 Configurar Domínio Customizado (opcional)

1. Clicar no serviço (Backend ou Frontend)
2. Ir em "Settings"
3. Em "Domains" clicar em "Generate Domain"
4. Railway gerará um domínio: `https://seu-app.up.railway.app`

---

## PARTE 5: Workflow de Atualização

### 5.1 Fazer mudanças localmente

```bash
# 1. Fazer alterações nos arquivos
# 2. Testar localmente
docker-compose up -d
```

### 5.2 Commitar e Push

```bash
# Adicionar mudanças
git add .

# Commit
git commit -m "feat: nova funcionalidade X"

# Push
git push origin main
```

### 5.3 Deploy Automático

Railway detecta automaticamente o push e faz deploy:

1. Acessa Railway dashboard
2. Verifica que deploy iniciou automaticamente
3. Aguarda conclusão (logs em tempo real)
4. Testa a aplicação online

---

## PARTE 6: Comandos Úteis

### Git

```bash
# Ver histórico de commits
git log --oneline

# Desfazer últimas mudanças (antes do commit)
git restore arquivo.py

# Desfazer último commit (mantém mudanças)
git reset --soft HEAD~1

# Ver diferenças
git diff

# Ver branches
git branch

# Criar nova branch
git checkout -b feature/nova-funcionalidade

# Mudar de branch
git checkout main

# Merge de branches
git merge feature/nova-funcionalidade

# Pull (baixar mudanças do GitHub)
git pull origin main
```

### Railway CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Linkar projeto
railway link

# Ver logs
railway logs

# Executar comando no container
railway run python manage.py

# Ver status
railway status

# Fazer deploy manual
railway up
```

### Docker (local)

```bash
# Subir todos os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar todos
docker-compose down

# Rebuild
docker-compose up -d --build

# Ver containers rodando
docker-compose ps
```

---

## PARTE 7: Checklist de Deploy

### Antes do primeiro deploy:

- [ ] Arquivo .gitignore configurado
- [ ] .env NÃO commitado
- [ ] SECRET_KEY forte gerada
- [ ] Dependências atualizadas (requirements.txt, package.json)
- [ ] Testes passando
- [ ] Dockerfile otimizado
- [ ] Variáveis de ambiente documentadas

### Para cada deploy:

- [ ] Código testado localmente
- [ ] Commit com mensagem descritiva
- [ ] Push para GitHub
- [ ] Verificar logs no Railway
- [ ] Testar aplicação online
- [ ] Verificar migrations aplicadas
- [ ] Verificar health check (`/health`)

---

## PARTE 8: Monitoramento

### 8.1 Railway Dashboard

- Logs em tempo real
- Métricas (CPU, RAM, Network)
- Alertas de erro

### 8.2 Logs Estruturados

Acessar logs JSON:
```bash
railway logs --json
```

### 8.3 Health Checks

Endpoint de saúde:
```
GET https://seu-backend.railway.app/health
```

Resposta esperada:
```json
{"status": "healthy"}
```

---

## PARTE 9: Troubleshooting

### Deploy falhou no Railway

1. Ver logs do deployment
2. Verificar se Dockerfile está correto
3. Verificar variáveis de ambiente
4. Verificar se migrations rodaram

### App não inicia

1. Verificar logs: `railway logs`
2. Verificar se portas estão corretas (8000 backend, 3000 frontend)
3. Verificar se DATABASE_URL está configurado
4. Verificar se dependências estão instaladas

### Migrations não aplicadas

```bash
railway run alembic upgrade head
```

### Dados não persistem

1. Verificar se volumes estão configurados
2. Railway persiste automaticamente PostgreSQL
3. Arquivos em `/data` podem ser perdidos (usar S3/cloud storage para produção)

---

## PARTE 10: Próximos Passos

### Segurança

1. Rotacionar API keys regularmente
2. Configurar HTTPS (Railway faz automaticamente)
3. Implementar rate limiting (já implementado)
4. Monitorar acessos suspeitos

### Performance

1. Adicionar CDN para frontend
2. Configurar cache Redis (já configurado)
3. Otimizar queries (já otimizado com joinedload)
4. Monitoring com Sentry

### Backups

1. Railway faz backup automático do PostgreSQL
2. Configurar backup dos uploads para S3
3. Backup do código está no GitHub

---

## Resumo Rápido

```bash
# Setup inicial (uma vez)
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USER/REPO.git
git push -u origin main

# Rotina diária
git add .
git commit -m "feat: descrição"
git push origin main

# Railway detecta e faz deploy automaticamente!
```

**Pronto!** Seu sistema está versionado no Git e com deploy automático no Railway.
