# Documentação Detalhada: Fluxo de Cotação Automatizada

**Data:** 12 de Dezembro de 2025
**Versão:** 1.0
**Sistema:** Plataforma de Cotação Automatizada

---

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Fluxo Detalhado de Processamento](#fluxo-detalhado-de-processamento)
4. [Componentes Principais](#componentes-principais)
5. [Integrações Externas](#integrações-externas)
6. [Custos e Tracking Financeiro](#custos-e-tracking-financeiro)
7. [Tratamento de Erros](#tratamento-de-erros)
8. [Otimizações e Performance](#otimizações-e-performance)

---

## Visão Geral

O sistema de cotação automatizada processa requisições de cotação através de dois fluxos principais:

1. **Cotação por Imagem**: Usuário envia foto(s) do produto
2. **Cotação por Texto**: Usuário digita descrição do produto

Ambos os fluxos convergem para um pipeline unificado que:
- Usa IA (Claude/Anthropic) para análise e extração de especificações
- Busca produtos em marketplaces (via SerpAPI)
- Extrai preços automaticamente (via web scraping com Playwright)
- Calcula estatísticas e detecta outliers
- Gera relatório em PDF (sob demanda)

---

## Arquitetura do Sistema

```
┌─────────────┐
│   Frontend  │ (Next.js 14 + React)
│  (Port 3000)│
└──────┬──────┘
       │ HTTP REST API
       ▼
┌─────────────┐
│   Backend   │ (FastAPI + Python)
│  (Port 8000)│
└──────┬──────┘
       │
       ├──────► PostgreSQL (dados persistentes)
       │
       ├──────► Redis (fila de tarefas)
       │
       └──────► Celery Worker (processamento assíncrono)
                    │
                    ├──► Anthropic API (análise IA)
                    ├──► SerpAPI (busca produtos)
                    └──► Playwright (scraping preços)
```

### Stack Tecnológica

**Backend:**
- Python 3.11+
- FastAPI (framework web)
- SQLAlchemy (ORM)
- Celery (processamento assíncrono)
- Redis (broker de mensagens)
- PostgreSQL (banco de dados)

**Frontend:**
- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- SWR (data fetching)

**Integrações:**
- Anthropic Claude API (análise IA)
- SerpAPI (busca em marketplaces)
- Playwright (web scraping)

---

## Fluxo Detalhado de Processamento

### Fase 1: Criação da Requisição (Frontend → Backend)

**Endpoint:** `POST /api/quotes`

**Parâmetros aceitos:**
```typescript
{
  inputText?: string,      // Descrição digitada (opcional)
  codigo?: string,         // Código do item (opcional)
  local?: string,          // Local da cotação
  pesquisador?: string,    // Nome do pesquisador
  project_id?: number,     // ID do projeto vinculado (opcional)
  images?: File[]          // Array de imagens (opcional)
}
```

**Validação:**
- Pelo menos `inputText` OU `images` deve ser fornecido
- Imagens são salvas em `storage/input_images/` com hash SHA256
- Registro é criado com `status = PROCESSING`

**Resposta:**
```json
{
  "quoteRequestId": 123
}
```

**Ação imediata:**
```python
# backend/app/api/quotes.py (linha ~83)
process_quote_request.delay(quote_request.id)
```

Isso enfileira a tarefa no Celery para processamento assíncrono.

---

### Fase 2: Processamento Assíncrono (Celery Worker)

**Task:** `process_quote_request(quote_request_id)`
**Arquivo:** `backend/app/tasks/quote_tasks.py`

#### Etapa 1: Inicialização (5%)

**Progresso exibido:**
```
"Carregando configurações e integrações..."
```

**Ações:**
1. Carrega API key da Anthropic (de `integration_settings` ou `settings.ANTHROPIC_API_KEY`)
2. Carrega modelo a ser usado (padrão: configurável, ex: `claude-3-5-sonnet-20241022`)
3. Inicializa cliente Claude
4. Carrega imagens do banco de dados (se houver)

**Código:**
```python
# Linha 62-84
_update_progress(db, quote_request, "initializing", 5,
    "Carregando configurações e integrações...")

api_key = _get_integration_setting(db, "ANTHROPIC", "api_key")
model = _get_integration_other_setting(db, "ANTHROPIC", "model")
claude_client = ClaudeClient(api_key=api_key, model=model)

input_images = db.query(File).filter(
    File.quote_request_id == quote_request_id,
    File.type == FileType.INPUT_IMAGE
).all()
```

---

#### Etapa 2: Análise de Entrada - IA (10%)

**Progresso exibido:**

**Se COM imagem:**
```
"Processando imagens e extraindo especificações técnicas..."
```

**Se SEM imagem (apenas texto):**
```
"Analisando descrição e identificando produto..."
```

**Ações:**
1. Envia para Claude API:
   - Texto descritivo (`inputText`)
   - Imagens (se houver) em base64
2. Claude retorna análise estruturada com:
   - `tipo_produto` (ex: "Cadeira Gamer")
   - `especificacoes_tecnicas` (dict com características)
   - `query_principal` (string de busca otimizada)
   - `queries_alternativas` (variações de busca)
   - `total_tokens_used` (para tracking de custo)

**Código:**
```python
# Linha 86-103
if image_data_list:
    _update_progress(db, quote_request, "analyzing_image", 10,
        "Processando imagens e extraindo especificações técnicas...")
else:
    _update_progress(db, quote_request, "analyzing_text", 10,
        "Analisando descrição e identificando produto...")

analysis_result = asyncio.run(
    claude_client.analyze_item(
        input_text=quote_request.input_text,
        image_files=image_data_list if image_data_list else None
    )
)

quote_request.claude_payload_json = analysis_result.dict()
quote_request.search_query_final = analysis_result.query_principal
db.commit()
```

**Exemplo de resposta do Claude:**
```json
{
  "tipo_produto": "Cadeira Gamer",
  "especificacoes_tecnicas": {
    "cor": "Preta",
    "material": "Couro sintético",
    "ajuste_altura": "Sim",
    "apoio_braco": "Regulável",
    "capacidade_peso": "120kg"
  },
  "query_principal": "cadeira gamer preta couro sintetico",
  "queries_alternativas": [
    "cadeira gamer ergonomica preta",
    "poltrona gamer reclinavel preta"
  ],
  "total_tokens_used": 1523
}
```

---

#### Etapa 2.5: Análise Completa - Tokens (30%)

**Progresso exibido:**
```
"Análise completa - [N] tokens processados pela IA"
```

**Ações:**
1. Registra custo da análise Claude no `financial_transactions`
2. Calcula custo baseado no modelo usado e tokens consumidos

**Código:**
```python
# Linha 107-115
if analysis_result.total_tokens_used > 0:
    _update_progress(db, quote_request, "analysis_complete", 30,
        f"Análise completa - {analysis_result.total_tokens_used} tokens processados pela IA")

    _register_anthropic_cost(db, quote_request, model,
        analysis_result.total_tokens_used)
```

**Cálculo de custo:**
```python
# Custos por modelo (exemplo)
# Claude 3.5 Sonnet: $3.00 / 1M input tokens, $15.00 / 1M output tokens
# Conversão para BRL usando taxa configurada
```

---

#### Etapa 3: Preparando Busca (40%)

**Progresso exibido:**
```
"Preparando busca de preços em lojas online..."
```

**Ações:**
1. Carrega API key do SerpAPI
2. Carrega parâmetros de busca:
   - `numero_cotacoes_por_pesquisa` (padrão: 3)
   - `tolerancia_outlier_percent` (padrão: 25%)
   - `serpapi_location` (padrão: "Brazil")
3. Inicializa `SerpApiProvider`

**Código:**
```python
# Linha 111-126
_update_progress(db, quote_request, "preparing_search", 40,
    "Preparando busca de preços em lojas online...")

serpapi_key = _get_integration_setting(db, "SERPAPI", "api_key")
serpapi_location = _get_parameter(db, "serpapi_location", "Brazil")

search_provider = SerpApiProvider(
    api_key=serpapi_key,
    engine=settings.SERPAPI_ENGINE,  # "google_shopping"
    location=serpapi_location
)

num_quotes = _get_parameter(db, "numero_cotacoes_por_pesquisa", 3)
outlier_tolerance = _get_parameter(db, "tolerancia_outlier_percent", 25) / 100
```

---

#### Etapa 4: Buscando Produtos (50%)

**Progresso exibido:**
```
"Buscando '[query]' em marketplaces..."
```

**Ações:**
1. Chama SerpAPI Google Shopping
2. Aplica filtro de outliers no nível da busca (otimização)
3. Retorna lista de produtos candidatos

**Código:**
```python
# Linha 132-143
_update_progress(db, quote_request, "searching_products", 50,
    f"Buscando '{analysis_result.query_principal}' em marketplaces...")

search_results = asyncio.run(
    search_provider.search_products(
        query=analysis_result.query_principal,
        limit=num_quotes,
        outlier_tolerance=outlier_tolerance
    )
)
```

**Otimização de chamadas de API:**
- **Estratégia antiga:** 1 Shopping + 1 Immersive por produto = 1 + N chamadas
- **Estratégia atual:** 1 Shopping + N Immersive (só produtos necessários) = N+1 chamadas
- O filtro de outliers é aplicado ANTES de fazer chamadas Immersive para economizar

**Estrutura do resultado:**
```python
@dataclass
class SearchResult:
    title: str          # "Cadeira Gamer XYZ"
    url: str            # Link da loja
    domain: str         # "www.exemplo.com.br"
    price: Decimal      # 399.90
    currency: str       # "BRL"
```

---

#### Etapa 5: Extraindo Preços (60%)

**Progresso exibido:**
```
"Acessando [N] lojas e capturando preços..."
```

**Ações:**
1. Para cada `SearchResult`:
   - Abre página com Playwright (navegador headless)
   - Captura screenshot da página
   - Extrai preço (tenta múltiplos seletores CSS)
   - Salva screenshot em `storage/screenshots/`
   - Cria registro em `quote_sources`
2. Valida preço > R$ 1,00
3. Limite de `num_quotes` fontes aceitas

**Código:**
```python
# Linha 147-197
_update_progress(db, quote_request, "extracting_prices", 60,
    f"Acessando {len(search_results)} lojas e capturando preços...")

valid_sources = []

async def extract_prices():
    async with PriceExtractor() as extractor:
        for result in search_results:
            if len(valid_sources) >= num_quotes:
                break

            try:
                screenshot_filename = f"screenshot_{quote_request_id}_{len(valid_sources)}.png"
                screenshot_path = os.path.join(
                    settings.STORAGE_PATH, "screenshots", screenshot_filename
                )

                price, method = await extractor.extract_price_and_screenshot(
                    result.url,
                    screenshot_path
                )

                if price and price > Decimal("1"):
                    # Salva screenshot no banco
                    screenshot_file = File(
                        type=FileType.SCREENSHOT,
                        mime_type="image/png",
                        storage_path=screenshot_path,
                        sha256=_calculate_sha256(screenshot_path)
                    )
                    db.add(screenshot_file)
                    db.flush()

                    # Cria fonte de cotação
                    source = QuoteSource(
                        quote_request_id=quote_request_id,
                        url=result.url,
                        domain=result.domain,
                        page_title=result.title,
                        price_value=price,
                        currency="BRL",
                        extraction_method=method,
                        screenshot_file_id=screenshot_file.id,
                        is_accepted=True
                    )
                    db.add(source)
                    valid_sources.append(source)

            except Exception as e:
                logger.error(f"Error extracting price from {result.url}: {str(e)}")
                continue

asyncio.run(extract_prices())
db.commit()
```

**Métodos de extração de preço:**
```python
class ExtractionMethod(enum.Enum):
    CSS_SELECTOR = "CSS_SELECTOR"      # Encontrou via seletor CSS
    TEXT_PATTERN = "TEXT_PATTERN"      # Encontrou via regex no HTML
    META_TAG = "META_TAG"              # Encontrou em meta tag OpenGraph
    JSON_LD = "JSON_LD"                # Encontrou em JSON-LD schema
```

**Seletores CSS tentados (em ordem):**
```python
PRICE_SELECTORS = [
    '[data-testid="price-value"]',
    '.price',
    '.product-price',
    '[itemprop="price"]',
    '.price-tag',
    // ... mais seletores
]
```

---

#### Etapa 6: Calculando Estatísticas (80%)

**Progresso exibido:**
```
"Analisando [N] preços coletados e calculando média..."
```

**Ações:**
1. Registra custo do SerpAPI (1 chamada por cotação)
2. Valida que pelo menos 1 preço foi extraído
3. Aplica detecção de outliers (IQR method)
4. Calcula estatísticas:
   - `valor_medio` (média dos preços aceitos)
   - `valor_minimo` (menor preço)
   - `valor_maximo` (maior preço)

**Código:**
```python
# Linha 202-225
_update_progress(db, quote_request, "calculating_stats", 80,
    f"Analisando {len(valid_sources)} preços coletados e calculando média...")

_register_serpapi_cost(db, quote_request, num_api_calls=1)

if not valid_sources:
    raise ValueError("No valid prices found")

# Detecta outliers usando IQR (Interquartile Range)
_apply_outlier_detection(db, valid_sources)
db.commit()

# Calcula estatísticas com preços aceitos (sem outliers)
accepted_sources = [s for s in valid_sources
                   if s.is_accepted and not s.is_outlier]

if accepted_sources:
    prices = [s.price_value for s in accepted_sources]
else:
    # Se todos forem outliers, usa todos os preços
    prices = [s.price_value for s in valid_sources]

quote_request.valor_medio = sum(prices) / len(prices)
quote_request.valor_minimo = min(prices)
quote_request.valor_maximo = max(prices)
```

**Algoritmo de detecção de outliers:**
```python
def _apply_outlier_detection(db: Session, sources: List[QuoteSource]):
    if len(sources) < 2:
        return  # Precisa de pelo menos 2 preços

    prices = [s.price_value for s in sources]

    # Calcula quartis
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    iqr = q3 - q1

    # Define limites
    lower_bound = q1 - (1.5 * iqr)
    upper_bound = q3 + (1.5 * iqr)

    # Marca outliers
    for source in sources:
        if source.price_value < lower_bound or source.price_value > upper_bound:
            source.is_outlier = True
            source.is_accepted = False
```

---

#### Etapa 7: Finalizando (95%)

**Progresso exibido:**
```
"Salvando resultados e finalizando cotação..."
```

**Ações:**
1. Salva todos os dados calculados
2. Marca status como `DONE`
3. Define progresso como 100%

**Código:**
```python
# Linha 227-237
_update_progress(db, quote_request, "finalizing", 95,
    "Salvando resultados e finalizando cotação...")

quote_request.status = QuoteStatus.DONE
quote_request.current_step = "completed"
quote_request.progress_percentage = 100
quote_request.step_details = "Cotação concluída! Preços capturados e analisados com sucesso."
db.commit()
db.refresh(quote_request)

logger.info(f"Quote request {quote_request_id} completed successfully. "
           f"Average price: R$ {quote_request.valor_medio}")
```

---

### Fase 3: Monitoramento em Tempo Real (Frontend)

**Componente:** `frontend/app/cotacao/[id]/page.tsx`

**Mecanismo de atualização:**
```typescript
const { data: quote, error, mutate } = useSWR<QuoteDetail>(
  id ? `/quotes/${id}` : null,
  () => quotesApi.get(id),
  {
    refreshInterval: (data) => {
      // Polling a cada 3 segundos se ainda está processando
      return data?.status === 'PROCESSING' ? 3000 : 0
    },
  }
)
```

**Interface exibida:**
```tsx
{quote.status === 'PROCESSING' && (
  <div className="card mb-6">
    <h2>Processamento em Andamento</h2>

    {/* Barra de progresso */}
    <div className="progress-bar">
      <div style={{ width: `${quote.progress_percentage}%` }} />
    </div>

    {/* Porcentagem */}
    <p>{quote.progress_percentage}%</p>

    {/* Descrição da etapa atual */}
    <p>{quote.step_details || 'Processando...'}</p>
  </div>
)}
```

---

## Componentes Principais

### 1. ClaudeClient (`backend/app/services/claude_client.py`)

**Responsabilidade:** Comunicação com Anthropic Claude API

**Método principal:**
```python
async def analyze_item(
    self,
    input_text: Optional[str] = None,
    image_files: Optional[List[bytes]] = None
) -> ItemAnalysisResult
```

**Prompt usado:**
```python
ANALYSIS_PROMPT = """
Você é um assistente especializado em análise de produtos para cotação de preços.

Analise o produto descrito abaixo e extraia:
1. Tipo do produto
2. Especificações técnicas
3. Query otimizada para busca em marketplaces
4. Queries alternativas

[input_text ou análise de imagem]

Retorne em formato JSON estruturado.
"""
```

**Configuração de contexto:**
- Max tokens: 4096
- Temperature: 0.2 (baixa variabilidade)
- Modelo: Configurável (ex: `claude-3-5-sonnet-20241022`)

---

### 2. SerpApiProvider (`backend/app/services/serpapi_provider.py`)

**Responsabilidade:** Busca de produtos via Google Shopping

**Método principal:**
```python
async def search_products(
    self,
    query: str,
    limit: int = 3,
    outlier_tolerance: float = 0.25
) -> List[SearchResult]
```

**Estratégia de busca:**
1. **Passo 1:** Chamada ao Google Shopping API
   ```python
   params = {
       "engine": "google_shopping",
       "q": query,
       "location": "Brazil",
       "hl": "pt-br",
       "gl": "br",
       "num": 20  # Busca mais resultados que o necessário
   }
   ```

2. **Passo 2:** Filtragem de outliers (baseado em preço)
3. **Passo 3:** Seleção dos N melhores produtos
4. **Passo 4:** Chamadas Immersive Product API (pegar URLs de lojas)

**Domínios bloqueados:**
```python
BLOCKED_DOMAINS = [
    'www.mercadolivre.com.br',
    'www.amazon.com.br',
    'www.olx.com.br',
    'www.shopee.com.br',
    'www.carrefour.com.br',
    'www.casasbahia.com.br'
]
```

---

### 3. PriceExtractor (`backend/app/services/price_extractor.py`)

**Responsabilidade:** Extração de preços de páginas web

**Tecnologia:** Playwright (navegador Chromium headless)

**Método principal:**
```python
async def extract_price_and_screenshot(
    self,
    url: str,
    screenshot_path: str
) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]
```

**Fluxo de extração:**
1. Abre página com Playwright
2. Aguarda carregamento (networkidle)
3. Tenta extrair preço em ordem de prioridade:
   - JSON-LD schema
   - Meta tags OpenGraph
   - Seletores CSS específicos
   - Regex no HTML
4. Captura screenshot full page
5. Retorna preço + método usado

**Configuração do navegador:**
```python
browser = await playwright.chromium.launch(
    headless=True,
    args=['--no-sandbox', '--disable-setuid-sandbox']
)

page = await browser.new_page(
    viewport={'width': 1920, 'height': 1080},
    user_agent='Mozilla/5.0 ...'
)
```

---

## Integrações Externas

### 1. Anthropic Claude API

**Endpoint:** `https://api.anthropic.com/v1/messages`

**Autenticação:** API Key no header `x-api-key`

**Custos (exemplo - Claude 3.5 Sonnet):**
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens

**Taxa de conversão:** Configurável em `integration_settings`

**Limites de rate:**
- 50 requests/minuto (tier padrão)
- 100,000 tokens/minuto

---

### 2. SerpAPI

**Endpoint:** `https://serpapi.com/search.json`

**Engines usadas:**
- `google_shopping` - Busca inicial de produtos
- `google_immersive_product` - Detalhes e links de lojas

**Autenticação:** Query param `api_key`

**Custos:**
- $50/mês para 5,000 buscas
- ~$0.01 por busca

**Estratégia de economia:**
- 1 Shopping + N Immersive = N+1 chamadas (otimizado)
- Filtro de outliers antes de Immersive calls

---

### 3. Playwright (Web Scraping)

**Setup:** Container Docker com Chromium incluído

**Configuração de timeout:**
```python
await page.goto(url, timeout=30000, wait_until='networkidle')
```

**Proteções anti-bot:**
- User-Agent customizado
- Viewport realista (1920x1080)
- Delays aleatórios
- Cookies aceitos automaticamente

**Rate limiting:** 1 request por segundo (configurável)

---

## Custos e Tracking Financeiro

### Modelo de Dados

**Tabela:** `financial_transactions`

```sql
CREATE TABLE financial_transactions (
    id SERIAL PRIMARY KEY,
    quote_request_id INTEGER REFERENCES quote_requests(id),
    transaction_type VARCHAR(50),  -- 'SERPAPI', 'ANTHROPIC'
    provider VARCHAR(50),
    cost_brl DECIMAL(12, 4),
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Registro de Custos

**1. Custo Anthropic:**
```python
def _register_anthropic_cost(
    db: Session,
    quote_request: QuoteRequest,
    model: str,
    tokens_used: int
):
    # Busca taxa de conversão USD -> BRL
    usd_to_brl = _get_parameter(db, "usd_to_brl_rate", 5.0)

    # Custos por modelo (USD)
    costs = {
        "claude-3-5-sonnet-20241022": {
            "input": 0.003,   # $3/1M tokens
            "output": 0.015   # $15/1M tokens
        }
    }

    # Assume 70% input, 30% output
    input_tokens = int(tokens_used * 0.7)
    output_tokens = int(tokens_used * 0.3)

    cost_usd = (
        (input_tokens / 1_000_000) * costs[model]["input"] +
        (output_tokens / 1_000_000) * costs[model]["output"]
    )

    cost_brl = Decimal(str(cost_usd * usd_to_brl))

    transaction = FinancialTransaction(
        quote_request_id=quote_request.id,
        transaction_type="ANTHROPIC",
        provider="ANTHROPIC",
        cost_brl=cost_brl,
        metadata_json={
            "model": model,
            "tokens_used": tokens_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd_to_brl": usd_to_brl
        }
    )
    db.add(transaction)
    db.commit()
```

**2. Custo SerpAPI:**
```python
def _register_serpapi_cost(
    db: Session,
    quote_request: QuoteRequest,
    num_api_calls: int = 1
):
    cost_per_call_brl = _get_parameter(db, "serpapi_cost_per_call_brl", 0.50)
    total_cost = Decimal(str(cost_per_call_brl * num_api_calls))

    transaction = FinancialTransaction(
        quote_request_id=quote_request.id,
        transaction_type="SERPAPI",
        provider="SERPAPI",
        cost_brl=total_cost,
        metadata_json={
            "num_api_calls": num_api_calls,
            "cost_per_call": cost_per_call_brl
        }
    )
    db.add(transaction)
    db.commit()
```

### Dashboard Financeiro

**Endpoint:** `GET /api/financial/summary`

**Métricas calculadas:**
- Custo total por período
- Custo médio por cotação
- Breakdown por provider (Anthropic vs SerpAPI)
- Tokens usados (total e média)

---

## Tratamento de Erros

### Hierarquia de Erros

```python
class QuoteProcessingError(Exception):
    """Erro base de processamento"""
    pass

class ClaudeAPIError(QuoteProcessingError):
    """Erro na API da Anthropic"""
    pass

class SerpAPIError(QuoteProcessingError):
    """Erro na API do SerpAPI"""
    pass

class PriceExtractionError(QuoteProcessingError):
    """Erro ao extrair preços"""
    pass
```

### Estratégia de Retry

**Celery Task:**
```python
@celery_app.task(
    base=QuoteTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60  # 1 minuto
)
def process_quote_request(self, quote_request_id: int):
    try:
        # ... processamento
    except (ClaudeAPIError, SerpAPIError) as exc:
        # Retry em erros de API externa
        raise self.retry(exc=exc, countdown=60)
    except Exception as exc:
        # Marca como ERROR sem retry
        quote_request.status = QuoteStatus.ERROR
        quote_request.error_message = str(exc)
        db.commit()
        raise
```

### Callback de Falha

```python
class QuoteTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Executado quando task falha definitivamente"""
        quote_request_id = args[0] if args else None
        if quote_request_id:
            db = SessionLocal()
            try:
                quote_request = db.query(QuoteRequest).filter(
                    QuoteRequest.id == quote_request_id
                ).first()

                if quote_request:
                    quote_request.status = QuoteStatus.ERROR
                    quote_request.error_message = str(exc)
                    quote_request.current_step = "error"
                    quote_request.progress_percentage = 0
                    quote_request.step_details = f"Erro: {str(exc)}"
                    db.commit()
            finally:
                db.close()
```

### Erros Comuns e Soluções

| Erro | Causa | Solução |
|------|-------|---------|
| `No valid prices found` | Nenhum preço extraído com sucesso | Verificar seletores CSS, testar URLs manualmente |
| `ANTHROPIC API rate limit` | Muitas requisições simultâneas | Configurar rate limiting no Celery |
| `SERPAPI quota exceeded` | Limite mensal atingido | Upgrade de plano ou aguardar reset |
| `Playwright timeout` | Página demorou muito para carregar | Aumentar timeout, verificar rede |
| `Screenshot save error` | Permissões de arquivo | Verificar permissões do diretório `storage/` |

---

## Otimizações e Performance

### 1. Otimização de Chamadas de API

**Problema original:**
- 1 Shopping call + 20 Immersive calls = 21 total calls
- Custo: $0.21 por cotação

**Solução implementada:**
```python
# Filtro de outliers ANTES de fazer Immersive calls
def search_products(self, query, limit=3, outlier_tolerance=0.25):
    # 1. Shopping call (retorna ~20 produtos)
    shopping_results = self._shopping_search(query)

    # 2. Filtra outliers (baseado em preço)
    filtered = self._filter_outliers(shopping_results, outlier_tolerance)

    # 3. Seleciona top N
    top_products = filtered[:limit]  # Apenas 3 produtos

    # 4. Immersive calls (só para os 3 selecionados)
    for product in top_products:
        immersive_data = self._immersive_search(product.token)

    return results  # 1 + 3 = 4 total calls
```

**Economia:** 80% de redução em chamadas de API

---

### 2. Caching de Resultados

**Redis cache para queries repetidas:**
```python
from redis import Redis
from functools import lru_cache

redis_client = Redis(host='redis', port=6379, db=0)

def search_products_cached(query: str, limit: int = 3):
    cache_key = f"search:{query}:{limit}"

    # Tenta buscar do cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Se não encontrou, faz busca real
    results = search_products(query, limit)

    # Salva no cache (TTL: 24 horas)
    redis_client.setex(
        cache_key,
        86400,  # 24 horas
        json.dumps(results, default=str)
    )

    return results
```

---

### 3. Paralelização de Scraping

**Extração de preços em paralelo:**
```python
async def extract_prices_parallel(urls: List[str]):
    async with PriceExtractor() as extractor:
        # Cria tasks assíncronas para todas as URLs
        tasks = [
            extractor.extract_price_and_screenshot(url, path)
            for url, path in zip(urls, screenshot_paths)
        ]

        # Executa todas em paralelo (máx 3 simultâneos)
        semaphore = asyncio.Semaphore(3)

        async def bounded_extract(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_extract(task) for task in tasks],
            return_exceptions=True
        )

        return [r for r in results if not isinstance(r, Exception)]
```

**Ganho:** 3x mais rápido (de ~30s para ~10s)

---

### 4. Database Query Optimization

**Uso de JOIN para evitar N+1:**
```python
# ❌ RUIM - N+1 queries
quote = db.query(QuoteRequest).filter(QuoteRequest.id == id).first()
sources = quote.sources  # Dispara query adicional
for source in sources:
    screenshot = source.screenshot_file  # Mais uma query por fonte!

# ✅ BOM - 1 query com JOIN
quote = db.query(QuoteRequest)\
    .options(
        joinedload(QuoteRequest.sources)
            .joinedload(QuoteSource.screenshot_file)
    )\
    .filter(QuoteRequest.id == id)\
    .first()
```

---

### 5. Índices de Banco de Dados

**Índices críticos:**
```sql
-- Busca rápida por ID de cotação
CREATE INDEX idx_quote_sources_quote_id ON quote_sources(quote_request_id);

-- Busca por projeto
CREATE INDEX idx_quote_requests_project_id ON quote_requests(project_id);

-- Busca por status
CREATE INDEX idx_quote_requests_status ON quote_requests(status);

-- Busca por data
CREATE INDEX idx_quote_requests_created_at ON quote_requests(created_at DESC);

-- Busca de transações financeiras
CREATE INDEX idx_financial_transactions_quote_id ON financial_transactions(quote_request_id);
CREATE INDEX idx_financial_transactions_created_at ON financial_transactions(created_at DESC);
```

---

## Diagrama de Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│                      INÍCIO: Usuário cria cotação           │
│         (POST /api/quotes com texto ou imagem)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend: Salva requisição + Enfileira task no Celery      │
│  Status: PROCESSING, progress: 0%                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Celery Worker: Inicia processamento assíncrono            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 1 (5%): Carregando configurações                    │
│  - Carrega API keys (Anthropic, SerpAPI)                   │
│  - Carrega parâmetros (num_quotes, outlier_tolerance)      │
│  - Inicializa clientes                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 2 (10%): Análise com IA                             │
│  ┌─────────────────────────────────────┐                   │
│  │ Se COM imagem:                      │                   │
│  │ "Processando imagens e extraindo    │                   │
│  │  especificações técnicas..."        │                   │
│  └─────────────────────────────────────┘                   │
│  ┌─────────────────────────────────────┐                   │
│  │ Se SEM imagem (só texto):           │                   │
│  │ "Analisando descrição e             │                   │
│  │  identificando produto..."          │                   │
│  └─────────────────────────────────────┘                   │
│                                                             │
│  Chama: claude_client.analyze_item()                       │
│  Retorna:                                                  │
│    - tipo_produto                                          │
│    - especificacoes_tecnicas                               │
│    - query_principal                                       │
│    - queries_alternativas                                  │
│    - total_tokens_used                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 2.5 (30%): Análise completa                         │
│  "Análise completa - [N] tokens processados pela IA"       │
│  - Registra custo Anthropic em financial_transactions      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 3 (40%): Preparando busca                           │
│  "Preparando busca de preços em lojas online..."           │
│  - Inicializa SerpApiProvider                              │
│  - Carrega parâmetros de busca                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 4 (50%): Buscando produtos                          │
│  "Buscando '[query]' em marketplaces..."                   │
│  - SerpAPI Google Shopping (1 call)                        │
│  - Filtra outliers                                         │
│  - SerpAPI Immersive Product (N calls para top produtos)   │
│  Total calls: N+1                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 5 (60%): Extraindo preços                           │
│  "Acessando [N] lojas e capturando preços..."              │
│  Para cada resultado:                                      │
│    1. Playwright abre página                               │
│    2. Captura screenshot                                   │
│    3. Extrai preço (CSS/regex/JSON-LD)                     │
│    4. Salva em quote_sources                               │
│  Paralelização: máx 3 simultâneos                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 6 (80%): Calculando estatísticas                    │
│  "Analisando [N] preços coletados e calculando média..."   │
│  - Registra custo SerpAPI                                  │
│  - Aplica detecção de outliers (IQR method)                │
│  - Calcula: valor_medio, valor_minimo, valor_maximo        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 7 (95%): Finalizando                                │
│  "Salvando resultados e finalizando cotação..."            │
│  - Salva tudo no banco                                     │
│  - Status: DONE                                            │
│  - Progress: 100%                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ETAPA 8 (100%): Concluído                                 │
│  "Cotação concluída! Preços capturados e analisados        │
│   com sucesso."                                            │
│  - Usuário pode gerar PDF sob demanda                      │
│  - Usuário pode vincular com tabela de materiais           │
└─────────────────────────────────────────────────────────────┘
```

---

## Resumo de Tempos Médios

| Etapa | Tempo Médio | Descrição |
|-------|-------------|-----------|
| Inicialização | 1-2s | Carregamento de configs |
| Análise IA | 3-5s | Anthropic API call |
| Preparação busca | 0.5s | Setup SerpAPI |
| Busca produtos | 2-3s | Shopping + Immersive calls |
| Extração preços | 10-15s | Playwright scraping (3 lojas) |
| Cálculo stats | 0.5s | Processamento local |
| Finalização | 0.5s | Salvar no DB |
| **TOTAL** | **18-27s** | **Cotação completa** |

---

## Checklist de Revisão do Fluxo

- [ ] Validar que descrições não têm mais "Etapa X:"
- [ ] Verificar diferenciação entre fluxo de imagem vs texto
- [ ] Confirmar que custos estão sendo registrados corretamente
- [ ] Testar detecção de outliers com diferentes cenários
- [ ] Validar screenshots sendo salvos corretamente
- [ ] Verificar comportamento quando 0 preços são encontrados
- [ ] Testar retry em caso de falha de API externa
- [ ] Confirmar que progress bar atualiza em tempo real
- [ ] Validar cálculo de estatísticas (média, min, max)
- [ ] Testar geração de PDF após conclusão

---

**Fim da Documentação**

*Para dúvidas ou sugestões de melhorias neste fluxo, consulte o time de desenvolvimento.*
