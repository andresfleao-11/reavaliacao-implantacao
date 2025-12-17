# Sistema de Cotação de Preços via SerpAPI

> **Versão:** 5.0
> **Data:** 17/Dezembro/2024
> **Objetivo:** Obter **N cotações válidas de um ÚNICO BLOCO** de produtos, garantindo que a variação de preço entre a menor e maior cotação não exceda X%.

---

## Regra Fundamental

> **A cotação só é concluída com sucesso quando NUM_COTACOES produtos são validados DENTRO DO MESMO BLOCO.** O bloco é a unidade que garante a variação máxima de preço entre as cotações.

---

## Parâmetros do Sistema

| Parâmetro | Descrição | Valor Padrão |
|-----------|-----------|--------------|
| `NUM_COTACOES` | Qtd mínima de cotações válidas necessárias **no mesmo bloco** | 3 |
| `VAR_MAX_PERCENT` | Variação máxima permitida entre menor e maior preço | 25% |
| `MAX_VALID_PRODUCTS` | Limite de produtos para processamento | 150 |
| `INCREMENTO_VAR` | Aumento absoluto de tolerância quando não há solução | 5% |
| `DOMINIOS_BLOQUEADOS` | Lista de domínios não permitidos | [...] |
| `VALIDAR_PRECO_SITE` | Habilita/desabilita verificação de divergência de preço | true/false |
| `PRICE_MISMATCH_TOLERANCE` | Tolerância entre preço Google e site (quando habilitado) | 5% |

---

## ETAPA 1: Processamento Google Shopping

### 1.1 Extração
Extrair de cada produto:
- `position`, `title`, `source`, `extracted_price`, `serpapi_immersive_product_api`

### 1.2 Filtros Eliminatórios
Descartar se:
- `source` está em `DOMINIOS_BLOQUEADOS`
- `extracted_price` é `null`, zero ou não-numérico

### 1.3 Ordenação e Limite
1. Ordenar por `extracted_price` crescente
2. Limitar a `MAX_VALID_PRODUCTS`

### 1.4 Formação de Blocos
Formar blocos consecutivos onde:
- Mínimo de `NUM_COTACOES` produtos
- Variação: `(preço_max - preço_min) / preço_min × 100 ≤ VAR_MAX_PERCENT`

**Seleção:** Priorizar maior bloco com menor preço inicial.

---

## ETAPA 2: Validação de Bloco (API Immersive)

### 2.1 Critérios de Falha do Produto

| Código | Falha se... | Obrigatório |
|--------|-------------|-------------|
| `NO_STORE_LINK` | API não retornou URL | ✓ Sempre |
| `BLOCKED_DOMAIN` | Domínio na lista de bloqueio | ✓ Sempre |
| `FOREIGN_DOMAIN` | TLD não é `.br` | ✓ Sempre |
| `DUPLICATE_DOMAIN` | Já existe cotação desta loja no bloco | ✓ Sempre |
| `LISTING_URL` | URL contém `/busca/`, `/search/`, `?q=`, `/categoria/`, `/colecao/`, `buscape`, `zoom` | ✓ Sempre |
| `PRICE_MISMATCH` | Preço do site difere > 5% do `extracted_price` | ⚙️ **Configurável** |
| `EXTRACTION_ERROR` | Não extraiu preço da página | ✓ Sempre |
| `INVALID_PRICE` | Preço extraído ≤ 1 ou > 10.000.000 | ✓ Sempre |

### 2.2 Comportamento do Parâmetro `VALIDAR_PRECO_SITE`

| `VALIDAR_PRECO_SITE` | Extrai preço do site? | Valida diferença? | Preço usado na cotação |
|----------------------|----------------------|-------------------|------------------------|
| `true` | ✓ Sim | ✓ Sim (rejeita se > 5%) | **Preço do SITE** |
| `false` | ✓ Sim (para screenshot) | ✗ Não | **Preço do GOOGLE** |

> **Importante:** Quando `VALIDAR_PRECO_SITE=false`, o sistema ainda visita o site para capturar screenshot, mas usa o `extracted_price` do Google Shopping como preço final. Isso garante consistência entre a seleção do bloco e a variação final.

### 2.3 Lógica de Validação do Bloco

```
produtos_validos_bloco = 0
produtos_falhados_bloco = 0

PARA cada produto do bloco (não testado anteriormente):
    resultado = validar_produto(produto)

    SE válido:
        produtos_validos_bloco++
        marcar produto como VALIDADO
    SENÃO:
        produtos_falhados_bloco++
        marcar produto como DESCARTADO

    // Verificar sucesso
    SE produtos_validos_bloco >= NUM_COTACOES:
        RETORNAR SUCESSO (cotação concluída!)

    // Verificar se ainda é possível atingir a meta neste bloco
    produtos_restantes = total_bloco - testados
    SE (produtos_validos_bloco + produtos_restantes) < NUM_COTACOES:
        BLOCO FALHOU → sair do loop
```

### 2.4 Quando o Bloco Falha: Recálculo

1. **Descartar** produtos que falharam na validação
2. **Preservar** produtos validados (não revalidar)
3. **Manter** produtos ainda não testados
4. **Reordenar** lista de produtos disponíveis por preço crescente
5. **Recalcular blocos** com os critérios originais
6. **Selecionar** próximo bloco elegível
7. **Repetir** validação (apenas para não testados do novo bloco)

### 2.5 Fallback: Aumento de Tolerância

Se **nenhum bloco** conseguir atingir `NUM_COTACOES` válidas:

1. `VAR_MAX_PERCENT = VAR_MAX_PERCENT + INCREMENTO_VAR`
2. Recalcular blocos com nova tolerância
3. Produtos já validados continuam validados
4. Repetir processo

---

## Fluxo Visual

```
┌────────────────────────────────────────────────────────────┐
│  ETAPA 1: GOOGLE SHOPPING                                  │
│  Extrair → Filtrar → Ordenar → Formar Blocos               │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  ETAPA 2: VALIDAÇÃO DE BLOCO                               │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Selecionar Bloco (maior tamanho, menor preço)        │  │
│  └──────────────────────────┬───────────────────────────┘  │
│                             ▼                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Validar produtos do bloco via Immersive API          │  │
│  │                                                      │  │
│  │   ✓ N válidos NO BLOCO? ──────────→ ✅ SUCESSO       │  │
│  │                                                      │  │
│  │   ✗ Impossível atingir N? ───┐                       │  │
│  └──────────────────────────────┼───────────────────────┘  │
│                                 ▼                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Recalcular blocos (sem descartados, com validados)   │  │
│  │                                                      │  │
│  │   Há blocos elegíveis? ──SIM──→ [voltar ao início]   │  │
│  │                          │                           │  │
│  │                         NÃO                          │  │
│  │                          ▼                           │  │
│  │   Aumentar VAR_MAX_PERCENT → Recalcular blocos       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## Implementação de Referência

### Estruturas de Dados

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from decimal import Decimal

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
    PRICE_MISMATCH = "price_mismatch"
    EXTRACTION_ERROR = "extraction_error"
    INVALID_PRICE = "invalid_price"

@dataclass
class Product:
    position: int
    title: str
    source: str
    extracted_price: float
    serpapi_immersive_product_api: Optional[str] = None
    status: ValidationStatus = ValidationStatus.PENDING
    failure_reason: Optional[FailureReason] = None
    site_price: Optional[float] = None
    site_domain: Optional[str] = None

@dataclass
class Block:
    products: List[Product]
    start_index: int
    min_price: float
    max_price: float

    @property
    def size(self) -> int:
        return len(self.products)

    @property
    def variation_percent(self) -> float:
        if self.min_price <= 0:
            return 0
        return (self.max_price - self.min_price) / self.min_price * 100
```

### Funções Principais

```python
def is_blocked_domain(source: str, blocked_domains: set) -> bool:
    """Verifica se o domínio está bloqueado"""
    source_lower = source.lower().strip()
    for blocked in blocked_domains:
        if blocked in source_lower:
            return True
    return False

def extract_and_filter_products(shopping_results: List[dict],
                                 blocked_domains: set) -> List[Product]:
    """ETAPA 1.1 e 1.2: Extração e Filtros Eliminatórios"""
    products = []
    for item in shopping_results:
        source = item.get("source", "")
        price = item.get("extracted_price")

        # Filtros
        if is_blocked_domain(source, blocked_domains):
            continue
        if price is None or price <= 0:
            continue

        products.append(Product(
            position=item.get("position", 0),
            title=item.get("title", ""),
            source=source,
            extracted_price=float(price),
            serpapi_immersive_product_api=item.get("serpapi_immersive_product_api")
        ))
    return products

def form_blocks(products: List[Product], var_max_percent: float,
                min_size: int) -> List[Block]:
    """ETAPA 1.4: Formação de Blocos"""
    blocks = []
    var_max = var_max_percent / 100

    for start_idx in range(len(products)):
        min_price = products[start_idx].extracted_price
        if min_price <= 0:
            continue

        max_allowed = min_price * (1 + var_max)

        block_products = []
        for product in products[start_idx:]:
            if product.extracted_price <= max_allowed:
                block_products.append(product)
            else:
                break

        if len(block_products) >= min_size:
            blocks.append(Block(
                products=block_products,
                start_index=start_idx,
                min_price=min_price,
                max_price=block_products[-1].extracted_price
            ))

    # Ordenar: maior tamanho, depois menor preço
    blocks.sort(key=lambda b: (-b.size, b.min_price))
    return blocks

def validate_product(product: Product,
                     validated_domains: set,
                     enable_price_mismatch: bool,
                     price_tolerance: float = 0.05) -> tuple:
    """
    Valida um produto via Immersive API.

    Retorna: (is_valid: bool, final_price: Decimal, failure_reason: Optional[FailureReason])
    """
    # 1. Obter URL da loja via Immersive API
    store_result = get_store_link(product)  # Implementar
    if not store_result:
        return False, None, FailureReason.NO_STORE_LINK

    # 2. Validações de domínio
    if is_blocked_domain(store_result.domain):
        return False, None, FailureReason.BLOCKED_DOMAIN
    if not store_result.domain.endswith('.br'):
        return False, None, FailureReason.FOREIGN_DOMAIN
    if store_result.domain in validated_domains:
        return False, None, FailureReason.DUPLICATE_DOMAIN
    if is_listing_url(store_result.url):
        return False, None, FailureReason.LISTING_URL

    # 3. Extrair preço do site
    site_price = extract_price(store_result.url)  # Implementar
    if not site_price or site_price <= 1:
        return False, None, FailureReason.EXTRACTION_ERROR

    # 4. Validar PRICE_MISMATCH (se habilitado)
    google_price = product.extracted_price
    if enable_price_mismatch:
        diff = abs(site_price - google_price) / google_price
        if diff > price_tolerance:
            return False, None, FailureReason.PRICE_MISMATCH
        final_price = Decimal(str(site_price))
    else:
        # Usar preço Google (consistente com seleção de bloco)
        final_price = Decimal(str(google_price))

    return True, final_price, None
```

### Loop Principal

```python
def process_quotation(shopping_results: List[dict],
                      num_quotes: int = 3,
                      var_max_percent: float = 25,
                      incremento_var: float = 5,
                      max_tolerance_increases: int = 10,
                      enable_price_mismatch: bool = True) -> dict:
    """
    Processa cotação seguindo a especificação completa.
    """
    # ETAPA 1: Processamento Google Shopping
    products = extract_and_filter_products(shopping_results, BLOCKED_DOMAINS)
    products.sort(key=lambda p: p.extracted_price)
    products = products[:MAX_VALID_PRODUCTS]

    # Estado global
    validated_domains = set()
    valid_sources = []

    # LOOP DE TOLERÂNCIA
    for tolerance_round in range(max_tolerance_increases + 1):
        if tolerance_round > 0:
            var_max_percent += incremento_var

        # LOOP DE BLOCOS
        while True:
            # Reconstruir lista sem produtos falhados
            available = [p for p in products if p.status != ValidationStatus.FAILED]
            if not available:
                break

            # Formar e selecionar bloco
            blocks = form_blocks(available, var_max_percent, num_quotes)
            if not blocks:
                break

            # Filtrar blocos elegíveis
            best_block = None
            for block in blocks:
                valid_count = sum(1 for p in block.products
                                  if p.status == ValidationStatus.VALID)
                pending_count = sum(1 for p in block.products
                                    if p.status == ValidationStatus.PENDING)
                if valid_count + pending_count >= num_quotes:
                    best_block = block
                    break

            if not best_block:
                break

            # Validar produtos do bloco
            valid_in_block = sum(1 for p in best_block.products
                                 if p.status == ValidationStatus.VALID)

            for product in best_block.products:
                if product.status != ValidationStatus.PENDING:
                    continue

                is_valid, final_price, failure = validate_product(
                    product, validated_domains, enable_price_mismatch
                )

                if is_valid:
                    product.status = ValidationStatus.VALID
                    product.site_price = float(final_price)
                    validated_domains.add(product.site_domain)
                    valid_sources.append((product, final_price))
                    valid_in_block += 1

                    if valid_in_block >= num_quotes:
                        # SUCESSO!
                        return {
                            "status": "SUCCESS",
                            "sources": valid_sources[-num_quotes:],
                            "variation": calculate_variation(valid_sources[-num_quotes:])
                        }
                else:
                    product.status = ValidationStatus.FAILED
                    product.failure_reason = failure

                # Verificar se bloco ainda é viável
                pending = sum(1 for p in best_block.products
                              if p.status == ValidationStatus.PENDING)
                if valid_in_block + pending < num_quotes:
                    break  # Bloco falhou, recalcular

    # Falha total
    return {"status": "FAILED", "sources": valid_sources}
```

---

## Domínios Bloqueados

```python
BLOCKED_DOMAINS = {
    # Marketplaces com proteção anti-bot
    "mercadolivre.com.br", "mercadolivre", "mercado livre",
    "shopee.com.br", "shopee",
    "amazon.com.br", "amazon.com", "amazon",
    "aliexpress.com", "aliexpress.com.br",
    "shein.com", "shein.com.br",
    "wish.com", "temu.com",

    # Grandes varejistas com anti-bot
    "casasbahia.com.br", "casas bahia",
    "magazineluiza.com.br", "magalu.com.br",
    "americanas.com.br", "submarino.com.br",
    "carrefour.com.br", "carrefour",
    "extra.com.br", "pontofrio.com.br",

    # Comparadores
    "buscape.com.br", "zoom.com.br", "bondfaro.com.br",

    # Internacionais
    "ebay.com", "ebay",
}
```

---

## Padrões de URL de Listagem

```python
LISTING_PATTERNS = [
    "/busca/", "/busca?",
    "/search/", "/search?",
    "/s?", "/s/",
    "?q=", "&q=", "query=",
    "/pesquisa/", "/pesquisa?",
    "/resultado",
    "/categoria/", "/categorias/", "/category/",
    "/colecao/", "/collection/",
    "/produtos?",
    "/list/", "/listing/", "/browse/",
    "/ofertas?",
    "/compare/", "/comparar/",
]

COMPARATOR_DOMAINS = ["buscape.com.br", "zoom.com.br", "bondfaro.com.br"]
```

---

## Status da Cotação

| Condição | Status |
|----------|--------|
| `fontes_validas >= NUM_COTACOES` | `DONE` |
| `fontes_validas > 0 AND < NUM_COTACOES` | `AWAITING_REVIEW` |
| `fontes_validas == 0` | `ERROR` |

---

## Métricas Salvas (search_stats)

```json
{
  "products_tested": 6,
  "blocks_recalculated": 2,
  "tolerance_increases": 0,
  "immersive_api_calls": 6,
  "final_valid_sources": 3,
  "initial_products_sorted": [...],
  "block_history": [
    {
      "iteration": 1,
      "tolerance_round": 0,
      "var_max_percent": 25.0,
      "total_blocks_formed": 10,
      "blocks_eligible": 10,
      "block_size": 5,
      "price_range": {"min": 714.51, "max": 810.00},
      "validated_in_block": 0,
      "untried_count": 5,
      "result": "failed"
    }
  ],
  "successful_products": [
    {
      "title": "Produto X",
      "source": "Loja Y",
      "google_price": 100.00,
      "extracted_price": 102.00,
      "final_price": 102.00,
      "price_source": "site",
      "url": "https://...",
      "domain": "loja.com.br"
    }
  ],
  "validation_failures": [...]
}
```

---

## Changelog

| Data | Versão | Alterações |
|------|--------|------------|
| Dez/2024 | 2.0 | Especificação inicial |
| Dez/2024 | 4.0 | Documentação do algoritmo real |
| 17/Dez/2024 | 5.0 | Correção: quando `VALIDAR_PRECO_SITE=false`, usar preço Google como `price_value` para garantir consistência com seleção de bloco |

---

## Arquivos de Implementação

| Arquivo | Função |
|---------|--------|
| `backend/app/tasks/quote_tasks.py` | Lógica principal de cotação |
| `backend/app/services/search_provider.py` | SerpAPI, validações, constantes |
| `backend/app/services/price_extractor.py` | Extração de preço via Playwright |
| `backend/app/models/quote_source_failure.py` | Modelo de falhas |
| `backend/tools/simulador_cotacao_v5.py` | Simulador de teste offline |
