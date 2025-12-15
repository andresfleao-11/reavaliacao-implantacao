# Documentacao Tecnica: Sistema de Cotacao de Precos

**Versao:** 1.0
**Data:** Dezembro 2024
**Sistema:** Reavaliacao Patrimonial

---

## Sumario

1. [Visao Geral](#1-visao-geral)
2. [Arquitetura do Sistema](#2-arquitetura-do-sistema)
3. [Mapeamento de Arquivos](#3-mapeamento-de-arquivos)
4. [Fluxo de Cotacao](#4-fluxo-de-cotacao)
5. [APIs Externas](#5-apis-externas)
6. [Validacoes de Produtos](#6-validacoes-de-produtos)
7. [Dominios Bloqueados](#7-dominios-bloqueados)
8. [Modelos de Dados](#8-modelos-de-dados)
9. [Configuracoes](#9-configuracoes)

---

## 1. Visao Geral

O sistema de cotacao de precos realiza pesquisa automatizada de valores de mercado para bens patrimoniais, seguindo as normas:

- **NBC TSP 07** (Ativo Imobilizado)
- **MCASP** (Manual de Contabilidade Aplicada ao Setor Publico)
- **Lei 14.133/2021** (Licitacoes e Contratos)

### Tipos de Entrada Suportados

| Tipo | Enum | Descricao |
|------|------|-----------|
| Texto | `TEXT` | Descricao textual do bem |
| Imagem | `IMAGE` | Foto do bem (OCR automatico) |
| Google Lens | `GOOGLE_LENS` | Identificacao visual via Google Lens |
| Lote Texto | `TEXT_BATCH` | Multiplos itens separados por ";" |
| Lote Imagens | `IMAGE_BATCH` | Multiplas imagens |
| Lote Arquivo | `FILE_BATCH` | Arquivo CSV ou XLSX |

---

## 2. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                   │
│                           (Next.js/React)                               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                    │
│                        (FastAPI + Celery)                               │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   quotes.py │  │ batch_      │  │ blocked_    │  │ debug_      │   │
│  │   (API)     │  │ quotes.py   │  │ domains.py  │  │ serpapi.py  │   │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘   │
│         │                │                                              │
│         └────────────────┼──────────────────────────────────────────┐  │
│                          │                                          │  │
│                          ▼                                          │  │
│  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │                      CELERY TASKS                               ││  │
│  │  ┌─────────────────┐  ┌─────────────────┐                       ││  │
│  │  │ quote_tasks.py  │  │ batch_tasks.py  │                       ││  │
│  │  └────────┬────────┘  └────────┬────────┘                       ││  │
│  └───────────┼────────────────────┼────────────────────────────────┘│  │
│              │                    │                                  │  │
│              └────────────────────┼──────────────────────────────┐  │  │
│                                   │                              │  │  │
│                                   ▼                              ▼  │  │
│  ┌─────────────────────────────────────────────────────────────────┐│  │
│  │                        SERVICES                                 ││  │
│  │                                                                 ││  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       ││  │
│  │  │ claude_       │  │ search_       │  │ price_        │       ││  │
│  │  │ client.py     │  │ provider.py   │  │ extractor.py  │       ││  │
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       ││  │
│  │          │                  │                  │                ││  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       ││  │
│  │  │ openai_       │  │ google_lens_  │  │ integration_  │       ││  │
│  │  │ client.py     │  │ service.py    │  │ logger.py     │       ││  │
│  │  └───────────────┘  └───────────────┘  └───────────────┘       ││  │
│  └─────────────────────────────────────────────────────────────────┘│  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   ANTHROPIC     │      │    SERPAPI      │      │   PLAYWRIGHT    │
│   CLAUDE API    │      │                 │      │   (Headless)    │
│                 │      │  - Shopping     │      │                 │
│  - Analise      │      │  - Immersive    │      │  - Screenshot   │
│  - OCR          │      │  - Google Lens  │      │  - Extracao     │
│  - Web Search   │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## 3. Mapeamento de Arquivos

### 3.1 Servicos (`backend/app/services/`)

#### `search_provider.py` - Provedor de Busca SerpAPI

| Classe/Funcao | Linha | Descricao |
|---------------|-------|-----------|
| `BLOCKED_DOMAINS` | 19-42 | Set com dominios bloqueados |
| `FOREIGN_DOMAIN_PATTERNS` | 45-59 | Padroes de dominios estrangeiros |
| `ALLOWED_FOREIGN_DOMAINS` | 63-80 | Excecoes permitidas |
| `SearchResult` | 83-91 | Modelo de resultado de busca |
| `SearchLog` | 94-110 | Log detalhado de operacoes |
| `ShoppingProduct` | 113-122 | Produto intermediario |
| `SerpApiProvider` | 136-1094 | **Implementacao principal** |
| `├─ search_products()` | 176-549 | Busca com blocos de variacao |
| `├─ _create_variation_blocks()` | 551-614 | Cria blocos (sliding window) |
| `├─ _search_google_shopping_raw()` | 616-714 | **Chamada Google Shopping** |
| `├─ _get_store_link()` | 716-753 | Obtem link da loja |
| `├─ _call_immersive_api()` | 755-925 | **Chamada Immersive API** |
| `├─ _is_blocked_domain()` | 997-1009 | Verifica bloqueio |
| `├─ _is_foreign_domain()` | 1011-1032 | Verifica estrangeiro |
| `└─ _is_blocked_source()` | 1034-1086 | Filtra fontes |

---

#### `claude_client.py` - Cliente Anthropic Claude

| Classe/Funcao | Linha | Descricao |
|---------------|-------|-----------|
| `ClaudeCallLog` | 12-19 | Modelo de log |
| `ItemAnalysisResult` | 21-37 | Resultado da analise |
| `ClaudeClient` | 39-840 | **Cliente principal** |
| `├─ _call_with_retry()` | 46-70 | Retry com backoff |
| `├─ analyze_item()` | 72-267 | **Analise de item** |
| `├─ _search_specs_on_web()` | 269-350 | Busca specs via web_search |
| `├─ _build_final_prompt()` | 352-465 | Prompt final |
| `├─ _analyze_text_only()` | 467-785 | **Analise somente texto** |
| `└─ _transform_patrimonial_response()` | 787-823 | Transforma resposta |

---

#### `openai_client.py` - Cliente OpenAI

| Classe/Funcao | Linha | Descricao |
|---------------|-------|-----------|
| `OpenAIClient` | 39-750 | **Cliente principal** |
| `├─ analyze_item()` | 72-250 | **Analise de item** |
| `├─ _build_final_prompt()` | 253-374 | Prompt final |
| `└─ _analyze_text_only()` | 376-695 | **Analise somente texto** |

---

#### `price_extractor.py` - Extrator de Precos

| Classe/Funcao | Linha | Descricao |
|---------------|-------|-----------|
| `PriceExtractor` | 12-510 | **Extrator com Playwright** |
| `├─ extract_price_and_screenshot()` | 39-101 | Acessa URL e extrai |
| `├─ _close_popups()` | 103-122 | Fecha popups/cookies |
| `├─ _extract_price()` | 361-374 | Orquestra extracao |
| `├─ _try_jsonld()` | 376-403 | Extrai de JSON-LD |
| `├─ _try_meta_tags()` | 405-439 | Extrai de meta tags |
| `└─ _try_dom_extraction()` | 441-470 | Extrai do DOM |

---

#### `google_lens_service.py` - Servico Google Lens

| Classe/Funcao | Linha | Descricao |
|---------------|-------|-----------|
| `upload_image_to_imgbb()` | 24-70 | Upload para imgbb |
| `GoogleLensService` | 108-484 | **Servico principal** |
| `├─ search_by_image_url()` | 124-192 | Busca por URL |
| `├─ extract_product_specs_from_url()` | 314-359 | Extrai specs |
| `└─ _extract_with_claude()` | 413-480 | Extrai com Claude |

---

### 3.2 Tasks Celery (`backend/app/tasks/`)

#### `quote_tasks.py` - Tasks de Cotacao

| Funcao | Linha | Descricao |
|--------|-------|-----------|
| `process_quote_request()` | 57-609 | **Task principal** |
| `_update_progress()` | 27-35 | Atualiza progresso |
| `_get_parameter()` | 644-676 | Busca parametro |
| `_register_ai_cost()` | 689-751 | Registra custo IA |
| `_register_serpapi_cost()` | 817-876 | Registra custo SerpAPI |

---

#### `batch_tasks.py` - Tasks de Lote

| Funcao | Linha | Descricao |
|--------|-------|-----------|
| `process_batch_job()` | 158-220 | **Coordenador de lote** |
| `process_batch_quote()` | 222-557 | Processa uma cotacao |
| `_update_batch_on_quote_complete()` | 560-596 | Atualiza lote |

---

### 3.3 API Endpoints (`backend/app/api/`)

#### `quotes.py` - Endpoints de Cotacao

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/quotes` | POST | Cria cotacao |
| `/api/quotes/{id}` | GET | Detalhes |
| `/api/quotes` | GET | Lista cotacoes |
| `/api/quotes/{id}/generate-pdf` | POST | Gera PDF |
| `/api/quotes/{id}/cancel` | POST | Cancela |
| `/api/quotes/{id}/requote` | POST | Recota |
| `/api/quotes/lens/search` | POST | **Busca Google Lens** |
| `/api/quotes/lens/create-quote` | POST | Cria do Lens |

---

#### `batch_quotes.py` - Endpoints de Lote

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/batch-quotes/text` | POST | Lote de texto |
| `/api/batch-quotes/images` | POST | Lote de imagens |
| `/api/batch-quotes/file` | POST | Lote de arquivo |
| `/api/batch-quotes/{id}` | GET | Status do lote |
| `/api/batch-quotes/{id}/cancel` | POST | Cancela lote |
| `/api/batch-quotes/{id}/resume` | POST | Retoma lote |

---

## 4. Fluxo de Cotacao

### 4.1 Diagrama Geral

```
 ENTRADA DO USUARIO
        │
        ├───────────┬───────────┬───────────┬─────────────┐
        │           │           │           │             │
        ▼           ▼           ▼           ▼             ▼
   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────┐
   │ TEXTO  │  │ IMAGEM │  │ GOOGLE │  │ LOTE   │  │  LOTE    │
   │        │  │ (OCR)  │  │ LENS   │  │ TEXTO  │  │ ARQUIVO  │
   └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └────┬─────┘
       │           │           │           │            │
       └───────────┴───────────┴───────────┴────────────┘
                               │
                               ▼
                    ┌──────────────────┐
                    │   API ENDPOINT   │
                    │  POST /api/quotes│
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  CELERY TASK     │
                    │  process_quote   │
                    │  _request()      │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ ETAPA 1 │         │ ETAPA 2 │         │ ETAPA 3 │
   │ ANALISE │         │ GOOGLE  │         │ IMMERSIVE│
   │ IA      │         │ SHOPPING│         │ API      │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        ▼                   ▼                   ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ ETAPA 4 │         │ ETAPA 5 │         │ ETAPA 6 │
   │ FILTRA  │         │ BLOCOS  │         │ EXTRAI  │
   │ FONTES  │         │ VARIACAO│         │ PRECOS  │
   └────┬────┘         └────┬────┘         └────┬────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │     ETAPA 7      │
                    │  CALCULO FINAL   │
                    │  (Media, Min,    │
                    │   Max, Variacao) │
                    └──────────────────┘
```

---

### 4.2 Etapa 1: Analise IA

#### Para entrada TEXTO:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROMPT PATRIMONIAL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Contexto: Especialista em pesquisa de precos para             │
│            reavaliacao patrimonial de orgaos publicos          │
│                                                                 │
│  Base normativa:                                                │
│  - NBC TSP 07 (Ativo Imobilizado)                              │
│  - MCASP                                                        │
│  - Lei 14.133/2021                                             │
│                                                                 │
│  Processo:                                                      │
│  1. Identificacao do bem (tipo, marca, modelo)                 │
│  2. Extracao de especificacoes (essenciais/complementares)     │
│  3. Construcao de query (4-8 termos, sem marca)                │
│                                                                 │
│  Saida JSON:                                                    │
│  - bem_patrimonial: {nome, marca, modelo, categoria}           │
│  - especificacoes: {essenciais, complementares}                │
│  - queries: {principal, alternativas, com_marca}               │
│  - busca: {palavras_chave, termos_excluir}                     │
│  - avaliacao: {confianca, completude_dados, observacoes}       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Para entrada IMAGEM:

```
┌─────────────────────────────────────────────────────────────────┐
│                       ETAPA 1: OCR                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Extrai de imagem:                                              │
│  - ocr_completo (todo texto visivel)                           │
│  - tipo_produto                                                 │
│  - marca                                                        │
│  - modelo                                                       │
│  - specs_visiveis                                               │
│  - tem_specs_relevantes (true/false)                           │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
          ┌─────────────────────┴─────────────────────┐
          │                                           │
          ▼                                           ▼
┌─────────────────────┐                   ┌─────────────────────┐
│ tem_specs = true    │                   │ tem_specs = false   │
│                     │                   │                     │
│ Vai direto para     │                   │ Chama web_search    │
│ geracao de query    │                   │ para buscar specs   │
│                     │                   │                     │
└─────────┬───────────┘                   └─────────┬───────────┘
          │                                         │
          └─────────────────────┬───────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ETAPA 3: GERA QUERY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Regras:                                                        │
│  - Query curta (max 60 chars)                                  │
│  - Specs mais importantes primeiro                              │
│  - SEM marca na query principal                                │
│  - Termos comerciais (gb, cm, pol, w)                          │
│                                                                 │
│  Exemplo: "notebook i5 8gb ssd 256gb 15.6 polegadas"           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.3 Etapa 2: Google Shopping API

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHAMADA SERPAPI                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GET https://serpapi.com/search                                │
│                                                                 │
│  Parametros:                                                    │
│  - engine: google_shopping                                      │
│  - q: "notebook i5 8gb ssd 256gb"                              │
│  - gl: br                                                       │
│  - hl: pt-br                                                    │
│  - google_domain: google.com.br                                │
│  - location: Brazil                                             │
│  - num: 100                                                     │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPOSTA                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  shopping_results: [                                            │
│    {                                                            │
│      "position": 1,                                             │
│      "title": "Notebook Dell Inspiron i5...",                  │
│      "price": "R$ 2.499,00",                                   │
│      "extracted_price": 2499.00,                               │
│      "source": "Casas Bahia",                                  │
│      "product_link": "https://google.com/...",                 │
│      "serpapi_immersive_product_api": "https://serpapi.com/..."│
│    },                                                           │
│    ...                                                          │
│  ]                                                              │
│                                                                 │
│  Total: 40-100 produtos                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.4 Etapa 3: Filtragem de Fontes

```
┌─────────────────────────────────────────────────────────────────┐
│                    FILTRO 1: DOMINIOS BLOQUEADOS                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Funcao: _is_blocked_source()                                   │
│                                                                 │
│  Bloqueados:                                                    │
│  ❌ mercadolivre.com.br (marketplace)                          │
│  ❌ amazon.com.br (anti-bot)                                   │
│  ❌ shopee.com.br (marketplace)                                │
│  ❌ aliexpress.com (internacional)                             │
│  ❌ casasbahia.com.br (cloudflare)                             │
│  ❌ magazineluiza.com.br (cloudflare)                          │
│  ❌ americanas.com.br (cloudflare)                             │
│  ... (ver lista completa na secao 7)                           │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FILTRO 2: PRECOS INVALIDOS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Condicao: extracted_price > 0                                  │
│                                                                 │
│  Remove produtos sem preco ou com preco zerado                  │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FILTRO 3: ORDENACAO                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  products.sort(key=extracted_price)                             │
│                                                                 │
│  Ordena do menor para o maior preco                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.5 Etapa 4: Criacao de Blocos de Variacao

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALGORITMO SLIDING WINDOW                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Parametro: variacao_maxima = 25%                               │
│                                                                 │
│  Exemplo com produtos:                                          │
│  [R$2.000, R$2.100, R$2.200, R$2.400, R$2.500, R$3.000]        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ BLOCO 1 (inicia R$2.000):                               │   │
│  │                                                          │   │
│  │   Max permitido = R$2.000 x 1.25 = R$2.500              │   │
│  │                                                          │   │
│  │   [R$2.000, R$2.100, R$2.200, R$2.400, R$2.500] ✓       │   │
│  │   R$3.000 > R$2.500 ✗                                   │   │
│  │                                                          │   │
│  │   Tamanho: 5 produtos                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ BLOCO 2 (inicia R$2.100):                               │   │
│  │                                                          │   │
│  │   Max permitido = R$2.100 x 1.25 = R$2.625              │   │
│  │                                                          │   │
│  │   [R$2.100, R$2.200, R$2.400, R$2.500] ✓                │   │
│  │                                                          │   │
│  │   Tamanho: 4 produtos                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Ordenacao dos blocos:                                          │
│  1. Mais produtos primeiro (maior chance de sucesso)           │
│  2. Menor preco inicial (opcoes mais baratas)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.6 Etapa 5: Immersive API

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHAMADA IMMERSIVE API                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Para cada produto no bloco:                                    │
│                                                                 │
│  GET https://serpapi.com/search                                │
│    ?engine=google_immersive_product                            │
│    &page_token=eyJ...                                          │
│    &api_key=***                                                │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPOSTA                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  {                                                              │
│    "product_results": {                                         │
│      "stores": [                                                │
│        {                                                        │
│          "name": "Leroy Merlin",                               │
│          "link": "https://www.leroymerlin.com.br/...",  ← LINK │
│          "price": "R$ 2.499,00",                               │
│          "extracted_price": 2499.00                            │
│        }                                                        │
│      ]                                                          │
│    },                                                           │
│    "online_sellers": [...]                                      │
│  }                                                              │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDACOES                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✓ _is_blocked_domain() - Dominio bloqueado?                   │
│  ✓ _is_foreign_domain() - Dominio estrangeiro?                 │
│  ✓ Dominio duplicado? - Ja temos fonte desse dominio?          │
│  ✓ _is_listing_url() - URL e pagina de listagem?               │
│  ✓ Price mismatch - Diferenca de preco > 15%?                  │
│                                                                 │
│  Se VALIDO → Adiciona aos resultados                           │
│  Se INVALIDO → Tenta proxima loja/produto                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.7 Etapa 6: Extracao de Precos

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLAYWRIGHT HEADLESS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Para cada fonte valida:                                        │
│                                                                 │
│  1. Abre URL no Chromium headless                              │
│     - User-Agent: Chrome 120                                   │
│     - Viewport: 1366x1229                                      │
│     - Locale: pt-BR                                            │
│                                                                 │
│  2. Fecha popups/cookies                                        │
│     - Botoes "Aceitar", "Concordo", "OK"                       │
│     - Botoes de fechar (X, close)                              │
│     - Remove overlays via JavaScript                           │
│                                                                 │
│  3. Captura screenshot                                          │
│     - Parte superior da pagina                                 │
│     - ~45% da altura total                                     │
│                                                                 │
│  4. Extrai preco (ordem de prioridade):                        │
│     a) JSON-LD (application/ld+json)                           │
│     b) Meta tags (og:price, twitter:data1)                     │
│     c) DOM selectors ([class*="price"], etc.)                  │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDACAO DE PRECO                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Se diferenca entre preco extraido e Google > 15%:             │
│    → Usa preco do Google (mais confiavel)                      │
│                                                                 │
│  Se extracao falha:                                             │
│    → Fallback para preco do Google Shopping                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.8 Etapa 7: Calculo Final

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESTATISTICAS                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  valor_medio = soma(precos) / quantidade                        │
│  valor_minimo = min(precos)                                     │
│  valor_maximo = max(precos)                                     │
│  variacao = (max / min - 1) * 100                              │
│                                                                 │
│  Exemplo com 3 fontes:                                          │
│  - R$ 2.400,00 (Loja A)                                        │
│  - R$ 2.499,00 (Loja B)                                        │
│  - R$ 2.550,00 (Loja C)                                        │
│                                                                 │
│  valor_medio = (2400 + 2499 + 2550) / 3 = R$ 2.483,00          │
│  valor_minimo = R$ 2.400,00                                     │
│  valor_maximo = R$ 2.550,00                                     │
│  variacao = (2550 / 2400 - 1) * 100 = 6,25%                    │
│                                                                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STATUS FINAL                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Se fontes >= N configurado:                                    │
│    → status = DONE ✓                                           │
│                                                                 │
│  Se fontes < N configurado:                                     │
│    → status = AWAITING_REVIEW ⚠                                │
│    (indica que precisa revisao manual)                         │
│                                                                 │
│  Se erro durante processamento:                                 │
│    → status = ERROR ✗                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. APIs Externas

### 5.1 Resumo de Custos

| API | Servico | Uso | Custo Aprox. |
|-----|---------|-----|--------------|
| **Anthropic Claude** | Analise de item | 1x por cotacao | ~$0.015 |
| **OpenAI GPT-4** | Analise de item (alternativo) | 1x por cotacao | ~$0.010 |
| **SerpAPI Shopping** | Busca de produtos | 1x por cotacao | ~$0.005 |
| **SerpAPI Immersive** | Link da loja | 3-10x por cotacao | ~$0.025 |
| **SerpAPI Lens** | Identificacao visual | 1x por busca | ~$0.010 |
| **imgbb** | Hospedagem de imagem | 1x por Lens | Gratuito |

**Custo medio por cotacao:** ~R$ 0,25 - R$ 0,40

---

### 5.2 Detalhes Anthropic Claude

```
Endpoint: https://api.anthropic.com/v1/messages

Modelos suportados:
- claude-sonnet-4-20250514 (padrao)
- claude-opus-4-5-20250101

Retry:
- Max retries: 5
- Backoff exponencial: 1s, 2s, 4s, 8s, 16s
- Trata erro 529 (overloaded): 5s, 10s, 15s, 20s, 25s

Tokens por cotacao (texto): ~3.000-4.000
Tokens por cotacao (imagem): ~4.000-6.000
```

---

### 5.3 Detalhes SerpAPI

```
Base URL: https://serpapi.com/search

Engines utilizados:
- google_shopping (busca de produtos)
- google_immersive_product (link da loja)
- google_lens (identificacao visual)

Parametros comuns:
- gl: br
- hl: pt-br
- google_domain: google.com.br
- location: Brazil

Rate limit:
- Max retries: 3
- Backoff: 2s, 4s, 8s
```

---

## 6. Validacoes de Produtos

| Local | Funcao | Validacao |
|-------|--------|-----------|
| search_provider.py:1034 | `_is_blocked_source()` | Fonte e marketplace bloqueado? |
| search_provider.py:997 | `_is_blocked_domain()` | Dominio tem anti-bot? |
| search_provider.py:1011 | `_is_foreign_domain()` | Dominio e estrangeiro? |
| search_provider.py:970 | `_is_listing_url()` | URL e pagina de listagem? |
| search_provider.py:819 | Price mismatch (Immersive) | Diferenca > 15%? |
| quote_tasks.py:402 | Price mismatch (Playwright) | Diferenca > 15%? |

---

## 7. Dominios Bloqueados

### 7.1 Marketplaces (anti-bot forte)

| Dominio | Motivo |
|---------|--------|
| mercadolivre.com.br | Marketplace com protecao anti-bot |
| mercadoshops.com.br | Extensao do ML |
| amazon.com.br | Cloudflare + anti-bot |
| amazon.com | Internacional |
| shopee.com.br | Marketplace |
| aliexpress.com | Internacional |
| shein.com | Internacional |
| wish.com | Internacional |
| temu.com | Internacional |

### 7.2 Varejistas com Cloudflare

| Dominio | Motivo |
|---------|--------|
| casasbahia.com.br | Cloudflare |
| pontofrio.com.br | Cloudflare |
| extra.com.br | Cloudflare |
| magazineluiza.com.br | Cloudflare |
| magalu.com.br | Cloudflare |
| americanas.com.br | Cloudflare |
| submarino.com.br | Cloudflare |
| shoptime.com.br | Cloudflare |
| carrefour.com.br | Cloudflare |

### 7.3 Dominios Estrangeiros Bloqueados

| Padrao | Descricao |
|--------|-----------|
| .com (sem .br) | Dominios genericos |
| .net | TLD generico |
| .org | TLD generico |
| .us, .uk, .de, .fr | Paises especificos |
| .cn, .jp | Asia |
| .eu | Europa |

### 7.4 Excecoes (dominios .com permitidos)

| Dominio | Motivo |
|---------|--------|
| lenovo.com | Fabricante com loja BR |
| dell.com | Fabricante com loja BR |
| hp.com | Fabricante com loja BR |
| samsung.com | Fabricante com loja BR |
| lg.com | Fabricante com loja BR |
| apple.com | Fabricante com loja BR |
| asus.com | Fabricante com loja BR |
| acer.com | Fabricante com loja BR |

---

## 8. Modelos de Dados

### 8.1 QuoteRequest

```python
class QuoteRequest(Base):
    id: int
    created_at: datetime
    updated_at: datetime
    status: QuoteStatus  # PROCESSING, DONE, ERROR, CANCELLED, AWAITING_REVIEW
    input_type: QuoteInputType  # TEXT, IMAGE, GOOGLE_LENS, *_BATCH

    project_id: int  # FK para projeto
    config_version_id: int  # FK para config do projeto

    input_text: str
    codigo_item: str

    claude_payload_json: dict  # Resposta completa da IA
    search_query_final: str  # Query usada na busca

    local: str
    pesquisador: str

    valor_medio: Decimal
    valor_minimo: Decimal
    valor_maximo: Decimal
    variacao_percentual: Decimal

    error_message: str

    # Progresso
    current_step: str
    progress_percentage: int  # 0-100
    step_details: str

    # Tentativas
    attempt_number: int
    original_quote_id: int  # FK para cotacao original (se recotacao)

    # Lote
    batch_job_id: int
    batch_index: int

    # Cache para retomada
    google_shopping_response_json: dict
    shopping_response_saved_at: datetime
```

### 8.2 QuoteSource

```python
class QuoteSource(Base):
    id: int
    quote_request_id: int  # FK

    url: str
    domain: str
    page_title: str

    price_value: Decimal
    currency: str  # BRL

    extraction_method: ExtractionMethod  # JSONLD, META, DOM, LLM

    screenshot_file_id: int  # FK para arquivo

    captured_at: datetime
    is_outlier: bool
    is_accepted: bool
```

### 8.3 QuoteStatus (Enum)

| Status | Cor | Descricao |
|--------|-----|-----------|
| PROCESSING | Azul | Em processamento |
| DONE | Verde | Concluido com sucesso |
| ERROR | Vermelho | Erro durante processamento |
| CANCELLED | Cinza | Cancelado pelo usuario |
| AWAITING_REVIEW | Amarelo | Menos fontes que o configurado |

---

## 9. Configuracoes

### 9.1 Parametros de Cotacao

| Parametro | Default | Descricao |
|-----------|---------|-----------|
| numero_cotacoes_por_pesquisa | 3 | Quantidade de fontes a obter |
| variacao_maxima_percent | 25 | Variacao maxima aceita entre fontes |
| serpapi_location | Brazil | Localizacao para busca |
| pesquisador_padrao | - | Pesquisador padrao do projeto |
| local_padrao | - | Local padrao do projeto |

### 9.2 Prioridade de Parametros

```
1. Configuracao do Projeto (config_version_id)
       ↓ (se nao encontrar)
2. Parametros Globais (settings)
       ↓ (se nao encontrar)
3. Valor Default
```

### 9.3 Variaveis de Ambiente

```bash
# IA
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
AI_PROVIDER=anthropic  # ou openai

# SerpAPI
SERPAPI_API_KEY=...
SERPAPI_ENGINE=google_shopping

# Storage
STORAGE_PATH=/app/storage

# imgbb (para Google Lens)
IMGBB_API_KEY=...
```

---

## Apendice: Exemplo de Log de Cotacao

```
=== Starting search: 'notebook i5 8gb ssd 256gb' ===
Parameters: limit=3, variacao_maxima=25%

Step 1: Got 40 raw products from Google Shopping
Step 2: 8 products after source filter (32 blocked)
Step 3: 8 products with valid prices (0 without price)
Step 4: 8 products (under limit of 150)
Step 5-6: Created 8 blocks, 5 valid (min size: 3)
    Block 1: 5 products (R$ 2400.00 - R$ 2999.00)
    Block 2: 4 products (R$ 2499.00 - R$ 3100.00)
    Block 3: 3 products (R$ 2550.00 - R$ 3100.00)

Step 7 (iteration 1): Block with 5 products
  Getting store link for 'Notebook Dell...' (R$ 2400.00) from Leroy Merlin
    API Call: Immersive Product
    → Got 3 stores from product_results
    ✓ Added [1/3]: leroymerlin.com.br - R$ 2400.00

  Getting store link for 'Notebook HP...' (R$ 2499.00) from Kabum
    API Call: Immersive Product
    ✓ Added [2/3]: kabum.com.br - R$ 2499.00

  Getting store link for 'Notebook Lenovo...' (R$ 2550.00) from Pichau
    API Call: Immersive Product
    ✓ Added [3/3]: pichau.com.br - R$ 2550.00

=== Search complete: 3 results (target: 3, used 3 Immersive API calls) ===
```

---

**Documento gerado automaticamente pelo sistema de Reavaliacao Patrimonial**
