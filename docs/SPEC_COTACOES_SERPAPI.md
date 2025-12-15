# Especificação: Sistema de Cotações via SerpAPI

> **Versão:** 2.0
> **Data:** Dezembro/2024
> **Atualizado:** Dezembro/2024
> **Objetivo:** Obter cotações válidas de produtos via Google Shopping + Google Immersive API

---

## 1. Visão Geral

O sistema busca produtos no Google Shopping via SerpAPI, valida cada produto através da API Immersive, e retorna um conjunto de cotações válidas respeitando critérios de variação de preço e quantidade mínima.

### Parâmetros de Configuração

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `max_price_variation` | Variação máxima permitida no bloco | 0.25 (25%) |
| `quotes_per_search` | Quantidade de cotações necessárias | 3 |
| `variation_increment` | Incremento quando falha | 0.20 (20%) |
| `max_variation_limit` | Limite máximo de variação | 0.50 (50%) |
| `max_valid_products` | Limite de produtos a processar | 150 |
| `blocked_domains` | Lista de domínios bloqueados | [...] |

---

## 2. Estruturas de Dados

### 2.1 Enums

```python
class ValidationStatus(Enum):
    PENDING = "pending"
    VALID = "valid"
    FAILED = "failed"

class FailureReason(Enum):
    NO_STORE_LINK = "no_store_link"
    BLOCKED_DOMAIN = "blocked_domain"
    FOREIGN_DOMAIN = "foreign_domain"
    DUPLICATE_DOMAIN = "duplicate_domain"
    LISTING_URL = "listing_url"
    EXTRACTION_ERROR = "extraction_error"
    PRICE_MISMATCH = "price_mismatch"  # Preço do site diferente do Google Shopping

class BlockStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    VALID = "valid"
    FAILED = "failed"
```

### 2.2 Dataclasses

```python
@dataclass
class ShoppingProduct:
    """Produto extraído do Google Shopping"""
    title: str
    price: str
    extracted_price: Optional[float]
    source: str
    serpapi_immersive_product_api: Optional[str]
    product_link: Optional[str]
    link: Optional[str]

@dataclass
class ProcessedProduct:
    """Produto com dados de validação"""
    title: str
    immersive_api_url: str
    source: str
    extracted_price: float
    store_link: Optional[str] = None
    validated: bool = False
    validation_status: ValidationStatus = ValidationStatus.PENDING
    failure_reason: Optional[FailureReason] = None

@dataclass
class QuotationBlock:
    """Bloco de produtos para cotação"""
    products: List[ProcessedProduct]
    min_price: float
    max_price: float
    variation_percentage: float
    status: BlockStatus = BlockStatus.PENDING
```

---

## 3. Fluxo - Etapa 1: Google Shopping

### 3.1 Extração de Dados
- **Entrada:** JSON da resposta SerpAPI
- **Campos:** `title`, `price`, `extracted_price`, `source`, `serpapi_immersive_product_api`, `product_link`, `link`

### 3.2 Filtro de Domínios Bloqueados
- Verificar `source` contra `blocked_domains`
- Normalizar domínios (lowercase, remover www.)
- **Descartar** produtos de domínios bloqueados

### 3.3 Filtro de Preços Inválidos
Remover produtos onde `extracted_price` é:
- `None`
- Zero (`0` ou `0.0`)
- Não conversível para número

### 3.4 Ordenação
```python
products.sort(key=lambda x: x.extracted_price)  # Crescente
```

### 3.5 Limitação
```python
products = products[:MAX_VALID_PRODUCTS]  # 150
```

### 3.6 Formação de Blocos

**Regras:**
- Variação máxima: `(max_price - min_price) / min_price <= max_variation`
- Mínimo de produtos: `quotes_per_search`
- Blocos com menos produtos são **DESCARTADOS**

**Algoritmo:**
1. Iniciar bloco com primeiro produto
2. Adicionar produtos enquanto variação <= limite
3. Quando variação exceder, fechar bloco (se >= mín) e iniciar novo
4. Descartar blocos com menos de `quotes_per_search` produtos

---

## 4. Fluxo - Etapa 2: Google Immersive

### 4.1 Validações do Produto

Cada produto deve passar por **TODAS** as validações na ordem:

| # | Validação | Condição de Falha | FailureReason |
|---|-----------|-------------------|---------------|
| 1 | Link de loja | API não retornou link válido | `NO_STORE_LINK` |
| 2 | Domínio bloqueado | Domínio em `blocked_domains` | `BLOCKED_DOMAIN` |
| 3 | Domínio brasileiro | TLD não é `.br` ou `.com.br` | `FOREIGN_DOMAIN` |
| 4 | Domínio duplicado | Já existe cotação deste domínio | `DUPLICATE_DOMAIN` |
| 5 | URL de listagem | URL contém padrões de busca | `LISTING_URL` |
| 6 | Extração de preço | Não conseguiu extrair preço | `EXTRACTION_ERROR` |
| 7 | Conferência de preço | Preço do site ≠ extracted_price | `PRICE_MISMATCH` |

### 4.2 Padrões de URL de Listagem

URLs rejeitadas se contiverem qualquer um dos padrões abaixo:

**Padrões de busca/pesquisa:**
- `/busca/`, `/busca?`
- `/search/`, `/search?`
- `/s?`, `/s/`
- `?q=`, `&q=`, `query=`
- `/pesquisa/`, `/pesquisa?`
- `/resultado`

**Padrões de categoria/listagem:**
- `/categoria/`, `/categorias/`, `/category/`
- `/colecao/`, `/collection/`
- `/produtos?`
- `/list/`, `/listing/`, `/browse/`
- `/ofertas?`

**Padrões de comparação:**
- `/compare/`, `/comparar/`

**Domínios de comparadores (sempre rejeitados):**
- `buscape.com.br`
- `zoom.com.br`
- `bondfaro.com.br`

**Regex para categorias genéricas:**
```regex
/(notebooks|celulares|eletronicos|informatica|tv|audio)/?(\?|$)
```

### 4.3 Validação de Preço - IMPORTANTE

**O preço extraído do site DEVE ser igual ao `extracted_price` do Google Shopping.**

Quando há diferença entre:
- Preço do Google Shopping (`extracted_price`)
- Preço extraído da página do produto (via Playwright)

→ **O produto FALHA na validação** (`PRICE_MISMATCH`)

**Tolerância:** Diferença de até **5%** é aceitável para compensar:
- Arredondamentos
- Variações de exibição (com/sem centavos)
- Atualizações recentes de preço

```python
def prices_match(site_price: float, google_price: float, tolerance: float = 0.05) -> bool:
    """Retorna True se os preços estão dentro da tolerância"""
    if google_price == 0:
        return False
    diff_percent = abs(site_price - google_price) / google_price
    return diff_percent <= tolerance
```

**Exemplo:**
- Google: R$ 100,00 | Site: R$ 102,00 → **OK** (2% diferença)
- Google: R$ 100,00 | Site: R$ 110,00 → **FALHA** (10% diferença)

### 4.4 Processamento de Bloco

```
PARA cada produto no bloco:
    SE produto.validation_status == VALID:
        contar como válido (já validado antes)
        CONTINUAR

    validar_produto(produto)

    SE produto válido:
        válidos++
        SE válidos >= quotes_per_search:
            RETORNAR SUCESSO
    SENÃO:
        SE válidos + restantes < quotes_per_search:
            BLOCO FALHOU (impossível atingir meta)
            SAIR do loop
```

---

## 5. Regras de Negócio Críticas

### RN01 - Produtos Já Validados
- **NÃO** são revalidados
- Sempre incluídos no pool de formação de blocos
- Domínios registrados para verificação de duplicidade

### RN02 - Produtos que Falharam
- **DESCARTADOS** permanentemente
- Não participam da reformação de blocos

### RN03 - Reformação de Blocos
Quando bloco falha:
1. Reunir: `validados + não_verificados` (sem falhos)
2. Reordenar por preço crescente
3. Reformar blocos com mesma variação
4. Continuar processamento

### RN04 - Incremento de Variação
Quando não é possível formar blocos válidos:
1. Aumentar variação: `nova = atual × (1 + variation_increment)`
   - Exemplo: 25% × 1.20 = 30%
2. Verificar se `nova_variação <= max_variation_limit`
3. Reformar blocos (sem revalidar produtos)
4. Se exceder limite → **FALHA FINAL**

**Sequência de incremento (variação inicial 25%):**
```
25% → 30% → 36% → 43.2% → 51.8% (excede 50%, FALHA)
```

### RN05 - Fórmula de Variação
```python
variacao = (preco_maximo - preco_minimo) / preco_minimo
```

### RN06 - Status da Cotação
Ao finalizar:
- Se `fontes_validas >= quotes_per_search` → `QuoteStatus.DONE`
- Se `fontes_validas > 0 AND fontes_validas < quotes_per_search` → `QuoteStatus.AWAITING_REVIEW`
- Se `fontes_validas == 0` → `QuoteStatus.ERROR`

---

## 6. Funções Auxiliares Implementadas

### 6.1 Constantes (search_provider.py)

```python
# Configuração de incremento de variação (RN04)
VARIATION_INCREMENT = 0.20  # 20% sobre o valor atual
MAX_VARIATION_LIMIT = 0.50  # 50% limite máximo

# Tolerância de validação de preço
PRICE_MISMATCH_TOLERANCE = 0.05  # 5% de tolerância
```

### 6.2 Funções de Variação

```python
def calculate_next_variation(current: float, increment: float = VARIATION_INCREMENT) -> float:
    """
    Calcula próxima variação aplicando incremento percentual.
    Exemplo: 0.25 * 1.20 = 0.30 (25% → 30%)
    """
    return current * (1 + increment)
```

### 6.3 Funções de Validação de Preço

```python
def prices_match(site_price: float, google_price: float, tolerance: float = PRICE_MISMATCH_TOLERANCE) -> bool:
    """
    Verifica se preços estão dentro da tolerância (default 5%).
    Retorna False se diferença > tolerância.
    """
    if google_price <= 0:
        return False
    diff_percent = abs(site_price - google_price) / google_price
    return diff_percent <= tolerance
```

### 6.4 Outras Funções (já implementadas)

| Função | Arquivo | Descrição |
|--------|---------|-----------|
| `_extract_domain(url)` | search_provider.py | Extrai domínio de URL |
| `_is_foreign_domain(domain)` | search_provider.py | Verifica se NÃO é .br |
| `_is_listing_url(url)` | search_provider.py | Verifica padrões de listagem |
| `_is_blocked_domain(domain)` | search_provider.py | Verifica domínios bloqueados |
| `_create_variation_blocks(...)` | search_provider.py | Forma blocos com variação |
| `extract_price_and_screenshot(...)` | price_extractor.py | Extrai preço via Playwright |

---

## 7. Fluxo Principal Resumido

```
1. Receber JSON do Google Shopping
2. Extrair e filtrar produtos (domínios, preços)
3. Ordenar por preço, limitar a 150
4. Formar blocos (variação ≤ 25%, mín 3)

5. LOOP principal:
   5.1 Processar bloco atual
   5.2 Validar produtos até atingir N válidos
   5.3 Se bloco OK → SUCESSO
   5.4 Se bloco falha → reformar com validados + pendentes
   5.5 Se sem blocos → aumentar variação +20%
   5.6 Se variação > limite → FALHA FINAL

6. Determinar status final:
   - fontes >= N → DONE
   - fontes > 0 e < N → AWAITING_REVIEW
   - fontes == 0 → ERROR

7. Retornar cotações válidas
```

---

## 8. Códigos de Erro/Log

| Código | Situação |
|--------|----------|
| `SHOPPING_EMPTY` | Nenhum produto retornado do Shopping |
| `ALL_FILTERED` | Todos produtos filtrados (domínio/preço) |
| `NO_VALID_BLOCKS` | Impossível formar blocos com mínimo de produtos |
| `VALIDATION_FAILED` | Produto falhou em validação específica |
| `BLOCK_FAILED` | Bloco não atingiu cotações necessárias |
| `VARIATION_EXCEEDED` | Atingiu limite máximo de variação |
| `PRICE_MISMATCH` | Preço do site diferente do Google Shopping |
| `SUCCESS` | Cotações obtidas com sucesso |
| `AWAITING_REVIEW` | Cotações insuficientes, requer revisão manual |

---

## 9. Domínios Bloqueados

```python
BLOCKED_DOMAINS = {
    # Marketplaces com proteção anti-bot forte
    "mercadolivre.com.br",
    "mercadoshops.com.br",
    "amazon.com.br",
    "amazon.com",
    "aliexpress.com",
    "aliexpress.com.br",
    "shopee.com.br",
    "shein.com",
    "shein.com.br",
    "wish.com",
    "temu.com",
    # Grandes varejistas com Cloudflare/anti-bot
    "carrefour.com.br",
    "casasbahia.com.br",
    "pontofrio.com.br",
    "extra.com.br",
    "magazineluiza.com.br",
    "magalu.com.br",
    "americanas.com.br",
    "submarino.com.br",
    "shoptime.com.br",
}
```

---

## 10. Domínios Estrangeiros Permitidos

Exceções ao filtro de domínios estrangeiros (fabricantes que vendem no Brasil):

```python
ALLOWED_FOREIGN_DOMAINS = {
    "lenovo.com",
    "dell.com",
    "hp.com",
    "samsung.com",
    "lg.com",
    "apple.com",
    "asus.com",
    "acer.com",
}
```

---

## 11. Status de Implementação

### Correções Implementadas (Dez/2024)

| # | Correção | Arquivo(s) | Status |
|---|----------|------------|--------|
| 1 | Validação de preço (5%, sem fallback) | search_provider.py, quote_tasks.py | IMPLEMENTADO |
| 2 | Status AWAITING_REVIEW | quote_tasks.py | IMPLEMENTADO |
| 3 | Incremento de variação ×1.20 | search_provider.py | IMPLEMENTADO |

### Funções Auxiliares Criadas

| Função | Local | Descrição |
|--------|-------|-----------|
| `calculate_next_variation()` | search_provider.py:27 | Calcula próxima variação |
| `prices_match()` | search_provider.py:41 | Valida preços com tolerância |

### Constantes Definidas

| Constante | Valor | Local |
|-----------|-------|-------|
| `VARIATION_INCREMENT` | 0.20 | search_provider.py:20 |
| `MAX_VARIATION_LIMIT` | 0.50 | search_provider.py:21 |
| `PRICE_MISMATCH_TOLERANCE` | 0.05 | search_provider.py:24 |

---

## 12. Changelog

| Data | Versão | Alterações |
|------|--------|------------|
| Dez/2024 | 2.0 | Especificação inicial documentada |
| Dez/2024 | 2.1 | Correção: incremento de variação é ×1.20, não +0.20 |
| Dez/2024 | 2.2 | Implementação completa: validação preço, AWAITING_REVIEW, incremento variação |
