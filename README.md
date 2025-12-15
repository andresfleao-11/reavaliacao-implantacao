# Sistema de Cotação de Preços

Sistema web MVP para cotação de produtos a partir de descrição e/ou imagens, com integração Claude (Anthropic) para OCR/visão/NLP e SerpAPI para busca automatizada.

## Características

- **Backend**: Python (FastAPI + SQLAlchemy + PostgreSQL)
- **Frontend**: Next.js (React + TypeScript)
- **IA**: Claude (Anthropic) para análise de imagens e texto
- **Busca**: SerpAPI para pesquisa de produtos
- **Extração**: Playwright para captura de preços e screenshots
- **Processamento**: Celery + Redis para tarefas assíncronas
- **PDF**: Geração de Ficha Individual de Cotação de Preços

## Funcionalidades

### Cotação
- Upload de imagens (etiquetas ou fotos do bem)
- Entrada de descrição textual
- Análise automática via Claude
- Busca automática de preços em marketplaces
- Detecção de outliers
- Cálculo de valor médio
- Geração de PDF multi-página com evidências

### Configurações
- **Parâmetros**: Número de cotações, tolerância de outliers, etc.
- **Banco de Preços**: Cadastro de itens com valores de mercado
- **Fator de Reavaliação**: Configuração de EC, PU, VUF e pesos
- **Integrações**: Configuração segura de chaves API (SerpAPI e Anthropic)

### Histórico
- Listagem de cotações anteriores
- Visualização de detalhes
- Download de PDFs gerados

## Pré-requisitos

- Docker e Docker Compose
- Chave API do SerpAPI (https://serpapi.com/)
- Chave API do Anthropic (https://console.anthropic.com/)

## Instalação e Execução

### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd "Projeto Reavaliacao"
```

### 2. Configure as variáveis de ambiente
```bash
cp .env.example .env
```

Edite o arquivo `.env` e adicione suas chaves:
```
SERPAPI_API_KEY=sua_chave_serpapi
ANTHROPIC_API_KEY=sua_chave_anthropic
SECRET_KEY=uma_chave_secreta_aleatoria_para_criptografia
```

### 3. Inicie os serviços com Docker Compose
```bash
docker-compose up -d
```

Isso iniciará:
- PostgreSQL (porta 5432)
- Redis (porta 6379)
- Backend FastAPI (porta 8000)
- Celery Worker
- Frontend Next.js (porta 3000)

### 4. Execute as migrations do banco
```bash
docker-compose exec backend alembic upgrade head
```

### 5. Acesse o sistema
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- API: http://localhost:8000

## Configuração Manual (Sem Docker)

### Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Instalar navegador Playwright
playwright install chromium

# Configurar .env
cp .env.example .env
# Edite o .env com suas configurações

# Executar migrations
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload

# Em outro terminal, iniciar Celery worker
celery -A app.tasks.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.local.example .env.local

# Iniciar servidor de desenvolvimento
npm run dev
```

## Uso do Sistema

### 1. Configurar Integrações (Primeiro Acesso)

1. Acesse **Configurações > Integrações**
2. Insira a chave da API SerpAPI
3. Clique em "Salvar" e depois em "Testar Conexão"
4. Insira a chave da API Anthropic (Claude)
5. Clique em "Salvar" e depois em "Testar Conexão"

### 2. Criar uma Cotação

1. Acesse **Cotação**
2. Digite a descrição do item OU faça upload de imagens
3. (Opcional) Preencha código, local e pesquisador
4. Clique em **Cotar**
5. Aguarde o processamento (polling automático a cada 3 segundos)

### 3. Visualizar Resultados

Após o processamento, você verá:
- Análise do Claude (nome, marca, modelo)
- Query de busca utilizada
- Lista de cotações encontradas
- Preços (com destaque para outliers)
- Screenshots das páginas
- Botão para baixar PDF

### 4. Consultar Histórico

1. Acesse **Histórico**
2. Visualize todas as cotações anteriores
3. Clique em "Ver detalhes" para abrir uma cotação
4. Baixe o PDF gerado

## Estrutura do Projeto

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # Rotas da API
│   │   ├── core/         # Configuração e segurança
│   │   ├── models/       # Modelos SQLAlchemy
│   │   ├── services/     # Claude, SerpAPI, PDF, etc.
│   │   ├── tasks/        # Tarefas Celery
│   │   └── main.py       # Aplicação FastAPI
│   ├── alembic/          # Migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/              # Páginas Next.js (App Router)
│   ├── components/       # Componentes React
│   ├── lib/              # API client
│   ├── package.json
│   └── Dockerfile
├── data/                 # Armazenamento de arquivos
│   ├── uploads/
│   ├── screenshots/
│   └── pdfs/
├── docker-compose.yml
└── README.md
```

## Endpoints da API

### Cotações

- `POST /api/quotes` - Criar cotação
- `GET /api/quotes/{id}` - Detalhes da cotação
- `GET /api/quotes` - Listar cotações (paginado)
- `GET /api/quotes/{id}/pdf` - Download do PDF
- `GET /api/quotes/{id}/screenshots/{file_id}` - Download de screenshot

### Configurações

- `GET/PUT /api/settings/parameters` - Parâmetros do sistema
- `GET/POST/PUT/DELETE /api/settings/bank-prices` - Banco de preços
- `GET/PUT /api/settings/revaluation` - Fator de reavaliação
- `GET/PUT /api/settings/integrations/{provider}` - Configuração de integrações
- `POST /api/settings/integrations/{provider}/test` - Testar integração

## Fluxo de Processamento

1. **Criação**: Usuário envia texto/imagens
2. **Análise**: Claude processa e retorna JSON estruturado
3. **Busca**: SerpAPI busca produtos com a query gerada
4. **Extração**: Playwright acessa cada URL, extrai preço e tira screenshot
5. **Outliers**: Sistema detecta preços fora da faixa de tolerância
6. **Estatísticas**: Calcula médio, mínimo e máximo
7. **PDF**: Gera documento com template oficial
8. **Persistência**: Salva tudo no banco de dados

## Testes

### Testes Unitários (Backend)

```bash
cd backend
pytest tests/unit/
```

### Testes de Integração (Backend)

```bash
cd backend
pytest tests/integration/
```

## Troubleshooting

### Erro ao conectar com PostgreSQL
- Verifique se o container está rodando: `docker-compose ps`
- Verifique as credenciais no `.env`

### Celery worker não processa tarefas
- Verifique se Redis está rodando
- Verifique logs: `docker-compose logs celery-worker`

### Playwright não consegue tirar screenshots
- O navegador Chromium deve ser instalado: `playwright install chromium`
- No Docker, já está incluído no Dockerfile

### Chaves API inválidas
- Teste as chaves manualmente em Configurações > Integrações
- Verifique se não há espaços extras nas chaves

## Segurança

- As chaves API são criptografadas antes de serem salvas no banco
- Nunca são enviadas ao frontend em texto plano
- Use HTTPS em produção
- Altere o SECRET_KEY para um valor aleatório forte

## Melhorias Futuras

- Implementação completa de Banco de Preços (CRUD)
- Implementação completa de Fator de Reavaliação
- Autenticação e controle de acesso
- Integração com mais provedores de busca
- Suporte a mais formatos de imagem (PDF, TIFF)
- Relatórios e dashboards
- Export para Excel
- API para integração externa

## Licença

Este projeto é proprietário.

## Suporte

Para dúvidas ou problemas, entre em contato com a equipe de desenvolvimento.
