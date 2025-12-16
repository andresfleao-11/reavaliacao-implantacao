"""
Endpoint de Debug para SerpAPI.
Permite simular o processamento de um JSON do Google Shopping
e visualizar cada etapa do fluxo de cotacao.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from decimal import Decimal
import json
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User, Setting, IntegrationSetting
from app.services.search_provider import (
    BLOCKED_DOMAINS,
    FOREIGN_DOMAIN_PATTERNS,
    ALLOWED_FOREIGN_DOMAINS,
    SerpApiProvider
)
from app.core.config import settings
from app.core.security import decrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/debug-serpapi", tags=["Debug SerpAPI"])


class ProductInfo(BaseModel):
    """Informacoes de um produto do Google Shopping"""
    title: str
    price: str
    extracted_price: Optional[float]
    source: str
    domain: Optional[str]
    position: int
    is_blocked: bool
    block_reason: Optional[str]
    has_valid_price: bool
    serpapi_immersive_url: Optional[str]


class BlockInfo(BaseModel):
    """Informacoes de um bloco de variacao"""
    index: int
    size: int
    min_price: float
    max_price: float
    variation_percent: float
    products: List[Dict[str, Any]]
    is_valid: bool  # True se tem produtos suficientes


class StepResult(BaseModel):
    """Resultado de uma etapa do processamento"""
    step_number: int
    step_name: str
    description: str
    input_count: int
    output_count: int
    filtered_count: int
    details: Optional[Dict[str, Any]] = None


class ImmersiveResult(BaseModel):
    """Resultado de uma chamada ao Google Immersive"""
    product_title: str
    source: str
    google_price: float
    immersive_url: str
    stores_found: int
    stores: List[Dict[str, Any]]
    selected_store: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str]


class ProductValidation(BaseModel):
    """Validacao detalhada de um produto durante o processamento Immersive"""
    product_title: str
    product_price: float
    product_source: str
    iteration: int
    block_index: int
    step: int  # Numero sequencial da validacao
    immersive_called: bool
    stores_returned: int
    validations: List[Dict[str, Any]]  # Lista de validacoes aplicadas
    final_status: str  # "SUCCESS", "FAILED", "SKIPPED"
    failure_reason: Optional[str]
    selected_store: Optional[Dict[str, Any]]


class BlockIteration(BaseModel):
    """Detalhes de uma iteracao de bloco"""
    iteration: int
    block_size: int
    block_min_price: float
    block_max_price: float
    products_processed: int
    results_obtained: int
    results_total: int
    failures_in_iteration: int
    total_failures: int
    skipped_reasons: Dict[str, int]
    status: str  # "SUCCESS", "FAILED", "CONTINUING"
    action: str  # "completed", "recreating_blocks", "trying_next_block"
    block_failure_reason: Optional[str] = None  # Motivo da falha do bloco
    failed_products_details: List[Dict[str, Any]] = []  # Detalhes dos produtos que falharam


class DebugResponse(BaseModel):
    """Resposta completa do debug"""
    success: bool
    query: str
    parameters: Dict[str, Any]
    steps: List[StepResult]
    blocks: List[BlockInfo]
    immersive_results: List[ImmersiveResult]
    product_validations: List[ProductValidation] = []  # Validacoes detalhadas
    block_iterations: List[BlockIteration] = []  # Iteracoes de blocos
    final_results: List[Dict[str, Any]]
    summary: Dict[str, Any]
    error: Optional[str] = None


def extract_price(price_str: str) -> Optional[float]:
    """Extrai valor numerico de uma string de preco"""
    if not price_str:
        return None
    import re
    # Remove currency symbols and extract number
    price_clean = re.sub(r'[R$\s.]', '', price_str).replace(',', '.')
    try:
        return float(price_clean)
    except ValueError:
        return None


def get_domain_from_source(source: str) -> str:
    """Extrai dominio de uma string source"""
    source_lower = source.lower()
    # Remove prefixos comuns
    for prefix in ['www.', 'http://', 'https://']:
        if source_lower.startswith(prefix):
            source_lower = source_lower[len(prefix):]
    # Pega apenas o dominio
    return source_lower.split('/')[0]


def is_blocked_source(source: str, blocked_domains: set = None) -> tuple:
    """
    Verifica se uma fonte esta bloqueada.
    Replica exatamente a logica de _is_blocked_source do search_provider.py
    Retorna (is_blocked, reason)
    """
    if blocked_domains is None:
        blocked_domains = BLOCKED_DOMAINS

    if not source:
        return False, None  # Empty source is not blocked, just ignored

    source_lower = source.lower()

    # Map common source names to their domains - EXATAMENTE como no search_provider.py
    source_to_domain_map = {
        "mercado livre": "mercadolivre.com.br",
        "mercadolivre": "mercadolivre.com.br",
        "amazon": "amazon.com.br",
        "amazon.com.br": "amazon.com.br",
        "shopee": "shopee.com.br",
        "aliexpress": "aliexpress.com",
        "shein": "shein.com",
        "wish": "wish.com",
        "temu": "temu.com",
        "carrefour": "carrefour.com.br",
        "casas bahia": "casasbahia.com.br",
        "ponto frio": "pontofrio.com.br",
        "extra": "extra.com.br",
        "magazine luiza": "magazineluiza.com.br",
        "magalu": "magalu.com.br",
        "americanas": "americanas.com.br",
        "submarino": "submarino.com.br",
        "shoptime": "shoptime.com.br",
    }

    # Check if the source matches any blocked domain mapping
    for source_name, domain in source_to_domain_map.items():
        if source_name in source_lower:
            if domain in blocked_domains:
                return True, f"source_map:{source_name}→{domain}"

    # Also check if the source directly contains a blocked domain's base name
    for blocked_domain in blocked_domains:
        base_name = blocked_domain.split('.')[0]
        if base_name in source_lower:
            return True, f"contains_blocked:{base_name}"

    return False, None


def is_foreign_domain(domain: str) -> tuple:
    """
    Verifica se um dominio e estrangeiro (nao brasileiro).
    Replica exatamente a logica de _is_foreign_domain do search_provider.py
    Retorna (is_foreign, reason)
    """
    if not domain:
        return False, None

    domain_lower = domain.lower()

    # Allow Brazilian domains
    if domain_lower.endswith(".com.br") or domain_lower.endswith(".br"):
        return False, None

    # Allow specific foreign domains (major manufacturers that sell in Brazil)
    if domain_lower in ALLOWED_FOREIGN_DOMAINS:
        return False, None

    # Check for foreign TLDs
    for pattern in FOREIGN_DOMAIN_PATTERNS:
        # Make sure we're checking the TLD, not part of the domain name
        if domain_lower.endswith(pattern) and not domain_lower.endswith(".com.br"):
            return True, f"foreign_domain:{pattern}"

    return False, None


def is_listing_url(url: str) -> tuple:
    """
    Verifica se a URL e uma pagina de busca/listagem em vez de pagina de produto.
    Replica exatamente a logica de _is_listing_url do search_provider.py
    Retorna (is_listing, reason)
    """
    if not url:
        return True, "empty_url"

    url_lower = url.lower()

    listing_patterns = [
        "/busca/", "/busca?", "/search/", "/search?",
        "/s?", "/s/", "?q=", "&q=", "query=",
        "/pesquisa/", "/pesquisa?", "/resultado",
        "/categoria/", "/categorias/", "/category/",
        "/colecao/", "/collection/", "/produtos?",
        "/list/", "/listing/", "/browse/",
        "buscape.com.br", "zoom.com.br", "bondfaro.com.br",
        "/compare/", "/comparar/", "/ofertas?"
    ]

    for pattern in listing_patterns:
        if pattern in url_lower:
            return True, f"listing_pattern:{pattern}"

    return False, None


def is_blocked_domain(domain: str) -> tuple:
    """
    Verifica se um dominio esta na lista de bloqueados.
    Retorna (is_blocked, reason)
    """
    if not domain:
        return False, None

    domain_lower = domain.lower()

    for blocked in BLOCKED_DOMAINS:
        if domain_lower == blocked or domain_lower.endswith("." + blocked):
            return True, f"blocked_domain:{blocked}"

    return False, None


def create_variation_blocks(products: List[Dict], variacao_maxima: float, min_block_size: int = 1) -> List[List[Dict]]:
    """
    Cria blocos de variacao a partir de uma lista de produtos.
    Replica a logica de _create_variation_blocks do search_provider.py
    """
    if not products:
        return []

    # Ordenar por preco
    sorted_products = sorted(products, key=lambda x: x['extracted_price'])

    # Filtrar precos invalidos
    sorted_products = [p for p in sorted_products if p.get('extracted_price') and p['extracted_price'] > 0]

    if not sorted_products:
        return []

    blocks = []

    for start_idx, start_product in enumerate(sorted_products):
        min_price = start_product['extracted_price']
        max_allowed_price = min_price * (1 + variacao_maxima)

        # Construir bloco
        block = []
        for product in sorted_products[start_idx:]:
            if product['extracted_price'] <= max_allowed_price:
                block.append(product)
            else:
                break

        # Apenas adicionar blocos que atendem o tamanho minimo
        if len(block) >= min_block_size:
            blocks.append(block)

    return blocks


@router.post("/analyze", response_model=DebugResponse)
async def analyze_shopping_json(
    file: UploadFile = File(...),
    limit: int = Form(default=3),
    variacao_maxima: float = Form(default=25.0),
    execute_immersive: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analisa um JSON do Google Shopping e simula todas as etapas do processamento.

    - file: Arquivo JSON com resposta do Google Shopping
    - limit: Numero de cotacoes desejadas (default: 3)
    - variacao_maxima: Variacao maxima em porcentagem (default: 25%)
    - execute_immersive: Se True, executa chamadas reais ao Google Immersive API
    """
    try:
        # Ler e parsear o JSON
        content = await file.read()
        try:
            shopping_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON invalido: {str(e)}")

        # Verificar se é o JSON da cotação (com raw_api_response) ou direto do SerpAPI
        if 'raw_api_response' in shopping_data:
            # JSON baixado da cotação - usar o raw_api_response
            raw_api_response = shopping_data.get('raw_api_response', {})
            if raw_api_response:
                shopping_data = raw_api_response
            else:
                raise HTTPException(status_code=400, detail="JSON da cotacao nao contem raw_api_response valido")

        # Extrair query da resposta
        query = shopping_data.get('search_parameters', {}).get('q', 'N/A')

        # Converter variacao para decimal
        variacao_decimal = variacao_maxima / 100.0

        steps = []
        all_products = []

        # ============================================
        # STEP 1: Extrair produtos do JSON
        # ============================================
        shopping_results = shopping_data.get('shopping_results', [])
        inline_results = shopping_data.get('inline_shopping_results', [])

        raw_products = []
        position = 0

        for item in shopping_results:
            position += 1
            # Usar extracted_price diretamente do JSON (já é um número)
            extracted = item.get('extracted_price')
            price_str = item.get('price', '')

            raw_products.append({
                'title': item.get('title', ''),
                'price': str(price_str),
                'extracted_price': float(extracted) if extracted is not None else None,
                'source': item.get('source', ''),
                'position': position,
                'serpapi_immersive_url': item.get('serpapi_product_api_immersive') or item.get('serpapi_immersive_product_api'),
                'product_link': item.get('product_link'),
                'link': item.get('link'),
            })

        for item in inline_results:
            position += 1
            # Usar extracted_price diretamente do JSON (já é um número)
            extracted = item.get('extracted_price')
            price_str = item.get('price', '')

            raw_products.append({
                'title': item.get('title', ''),
                'price': str(price_str),
                'extracted_price': float(extracted) if extracted is not None else None,
                'source': item.get('source', ''),
                'position': position,
                'serpapi_immersive_url': item.get('serpapi_product_api_immersive') or item.get('serpapi_immersive_product_api'),
                'product_link': item.get('product_link'),
                'link': item.get('link'),
            })

        steps.append(StepResult(
            step_number=1,
            step_name="Extracao de Produtos",
            description="Extrair todos os produtos do JSON do Google Shopping",
            input_count=len(shopping_results) + len(inline_results),
            output_count=len(raw_products),
            filtered_count=0,
            details={
                "shopping_results_count": len(shopping_results),
                "inline_results_count": len(inline_results),
                "total_raw": len(raw_products)
            }
        ))

        # ============================================
        # STEP 2: Filtrar fontes bloqueadas
        # ============================================
        products_step2 = []
        blocked_products = []
        blocked_reasons = {}

        for p in raw_products:
            is_blocked, reason = is_blocked_source(p['source'])
            p['is_blocked'] = is_blocked
            p['block_reason'] = reason
            p['domain'] = get_domain_from_source(p['source'])

            if is_blocked:
                blocked_products.append(p)
                blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
            else:
                products_step2.append(p)

        steps.append(StepResult(
            step_number=2,
            step_name="Filtro de Fontes Bloqueadas",
            description="Remover produtos de fontes bloqueadas (marketplaces, lojas com anti-bot)",
            input_count=len(raw_products),
            output_count=len(products_step2),
            filtered_count=len(blocked_products),
            details={
                "blocked_reasons": blocked_reasons,
                "blocked_domains_config": list(BLOCKED_DOMAINS)[:10],  # Primeiros 10
                "blocked_products": [
                    {"title": p['title'][:50], "source": p['source'], "reason": p['block_reason']}
                    for p in blocked_products[:10]  # Primeiros 10
                ]
            }
        ))

        # ============================================
        # STEP 3: Filtrar precos invalidos
        # ============================================
        products_step3 = []
        invalid_price_products = []

        for p in products_step2:
            p['has_valid_price'] = p['extracted_price'] is not None and p['extracted_price'] > 0
            if p['has_valid_price']:
                products_step3.append(p)
            else:
                invalid_price_products.append(p)

        steps.append(StepResult(
            step_number=3,
            step_name="Filtro de Precos Validos",
            description="Remover produtos sem preco ou com preco invalido",
            input_count=len(products_step2),
            output_count=len(products_step3),
            filtered_count=len(invalid_price_products),
            details={
                "invalid_price_products": [
                    {"title": p['title'][:50], "price": p['price']}
                    for p in invalid_price_products[:10]
                ]
            }
        ))

        # ============================================
        # STEP 4: Ordenar por preco e limitar a 150
        # ============================================
        products_step3.sort(key=lambda x: x['extracted_price'])

        MAX_PRODUCTS = 150
        products_step4 = products_step3[:MAX_PRODUCTS]

        steps.append(StepResult(
            step_number=4,
            step_name="Ordenacao e Limitacao",
            description=f"Ordenar por preco e limitar a {MAX_PRODUCTS} produtos",
            input_count=len(products_step3),
            output_count=len(products_step4),
            filtered_count=max(0, len(products_step3) - MAX_PRODUCTS),
            details={
                "max_products": MAX_PRODUCTS,
                "price_range": {
                    "min": products_step4[0]['extracted_price'] if products_step4 else None,
                    "max": products_step4[-1]['extracted_price'] if products_step4 else None
                },
                "products": [
                    {
                        "position": i + 1,
                        "title": p['title'][:60],
                        "price": p['extracted_price'],
                        "source": p['source'],
                        "has_immersive_api": bool(p.get('serpapi_immersive_url'))
                    }
                    for i, p in enumerate(products_step4)
                ]
            }
        ))

        # ============================================
        # STEP 5: Criar blocos de variacao
        # ============================================
        blocks = []
        valid_blocks = []

        for i, start_product in enumerate(products_step4):
            min_price = start_product['extracted_price']
            max_allowed = min_price * (1 + variacao_decimal)

            block_products = []
            for p in products_step4[i:]:
                if p['extracted_price'] <= max_allowed:
                    block_products.append(p)
                else:
                    break

            if len(block_products) > 0:
                variation = ((block_products[-1]['extracted_price'] / block_products[0]['extracted_price']) - 1) * 100
                block = BlockInfo(
                    index=i,
                    size=len(block_products),
                    min_price=block_products[0]['extracted_price'],
                    max_price=block_products[-1]['extracted_price'],
                    variation_percent=round(variation, 2),
                    products=[
                        {
                            "title": p['title'][:60],
                            "price": p['extracted_price'],
                            "source": p['source']
                        }
                        for p in block_products
                    ],
                    is_valid=len(block_products) >= limit
                )
                blocks.append(block)
                if block.is_valid:
                    valid_blocks.append(block)

        # Ordenar blocos validos por tamanho (desc) e preco minimo (asc)
        valid_blocks.sort(key=lambda b: (-b.size, b.min_price))

        steps.append(StepResult(
            step_number=5,
            step_name="Criacao de Blocos de Variacao",
            description=f"Criar blocos de produtos dentro de {variacao_maxima}% de variacao",
            input_count=len(products_step4),
            output_count=len(valid_blocks),
            filtered_count=len(blocks) - len(valid_blocks),
            details={
                "total_blocks_created": len(blocks),
                "valid_blocks": len(valid_blocks),
                "invalid_blocks": len(blocks) - len(valid_blocks),
                "min_products_per_block": limit,
                "top_5_blocks": [
                    {
                        "index": b.index,
                        "size": b.size,
                        "price_range": f"R$ {b.min_price:.2f} - R$ {b.max_price:.2f}",
                        "variation": f"{b.variation_percent:.1f}%"
                    }
                    for b in valid_blocks[:5]
                ]
            }
        ))

        # ============================================
        # STEP 6: Executar Google Immersive (opcional)
        # Com validacoes detalhadas e recriacao de blocos
        # ============================================
        immersive_results = []
        final_results = []
        product_validations = []
        block_iterations = []

        if execute_immersive and products_step4:
            # Obter API key do SerpAPI - mesma logica do settings.py
            serpapi_setting = db.query(IntegrationSetting).filter(
                IntegrationSetting.provider == "SERPAPI"  # UPPERCASE como no banco
            ).first()

            serpapi_key = None

            # Primeiro tenta do banco de dados
            if serpapi_setting and serpapi_setting.settings_json:
                encrypted_key = serpapi_setting.settings_json.get('api_key')
                if encrypted_key:
                    serpapi_key = decrypt_value(encrypted_key)

            # Fallback para variaveis de ambiente
            if not serpapi_key:
                serpapi_key = settings.SERPAPI_API_KEY

            if not serpapi_key:
                raise HTTPException(
                    status_code=400,
                    detail="API Key do SerpAPI nao encontrada. Configure em Configuracoes > Integracoes ou defina SERPAPI_API_KEY no .env"
                )

            import httpx
            from urllib.parse import urlparse

            # Estado do processamento iterativo
            failed_product_keys = set()
            results_by_key = {}
            urls_seen = set()  # URLs únicas (não mais domínios) - permite produtos diferentes do mesmo domínio
            iteration = 0
            max_iterations = 50
            validation_step = 0

            async with httpx.AsyncClient(timeout=30.0) as client:
                while len(final_results) < limit and iteration < max_iterations:
                    iteration += 1

                    # Recriar blocos excluindo produtos que falharam
                    products_for_blocks = [
                        p for p in products_step4
                        if f"{p['title']}_{p['extracted_price']}" not in failed_product_keys
                    ]

                    if not products_for_blocks:
                        block_iterations.append(BlockIteration(
                            iteration=iteration,
                            block_size=0,
                            block_min_price=0,
                            block_max_price=0,
                            products_processed=0,
                            results_obtained=0,
                            results_total=len(final_results),
                            failures_in_iteration=0,
                            total_failures=len(failed_product_keys),
                            skipped_reasons={},
                            status="FAILED",
                            action="no_products_left"
                        ))
                        break

                    # Criar blocos com produtos restantes
                    current_blocks = create_variation_blocks(products_for_blocks, variacao_decimal, limit)

                    if not current_blocks:
                        block_iterations.append(BlockIteration(
                            iteration=iteration,
                            block_size=0,
                            block_min_price=0,
                            block_max_price=0,
                            products_processed=0,
                            results_obtained=0,
                            results_total=len(final_results),
                            failures_in_iteration=0,
                            total_failures=len(failed_product_keys),
                            skipped_reasons={},
                            status="FAILED",
                            action="no_valid_blocks"
                        ))
                        break

                    # Ordenar blocos: maior tamanho primeiro, depois menor preco
                    current_blocks.sort(key=lambda b: (-len(b), b[0]['extracted_price']))

                    # Usar o melhor bloco
                    block = current_blocks[0]
                    block_min_price = block[0]['extracted_price']
                    block_max_price = block[-1]['extracted_price']

                    block_results_count = 0
                    block_skipped = {
                        "blocked_domain": 0, "foreign_domain": 0, "duplicate_url": 0,
                        "listing_url": 0, "no_store_link": 0, "no_immersive_url": 0,
                        "api_error": 0
                    }
                    new_failures = []
                    failed_products_details = []  # Detalhes dos produtos que falharam nesta iteração

                    for product in block:
                        if len(final_results) >= limit:
                            break

                        product_key = f"{product['title']}_{product['extracted_price']}"
                        validation_step += 1

                        # Pular produtos ja falhados
                        if product_key in failed_product_keys:
                            continue

                        # Verificar se ja temos resultado valido para este produto
                        if product_key in results_by_key:
                            stored = results_by_key[product_key]
                            if stored['store_link'] not in urls_seen:
                                urls_seen.add(stored['store_link'])
                                final_results.append(stored)
                                block_results_count += 1
                                product_validations.append(ProductValidation(
                                    product_title=product['title'][:60],
                                    product_price=product['extracted_price'],
                                    product_source=product['source'],
                                    iteration=iteration,
                                    block_index=0,
                                    step=validation_step,
                                    immersive_called=False,
                                    stores_returned=0,
                                    validations=[{"check": "reused_valid", "passed": True}],
                                    final_status="SUCCESS",
                                    failure_reason=None,
                                    selected_store=stored
                                ))
                            continue

                        # Verificar se tem URL do Immersive
                        if not product.get('serpapi_immersive_url'):
                            new_failures.append(product_key)
                            block_skipped["no_immersive_url"] += 1
                            failed_products_details.append({
                                "product_title": product['title'][:60],
                                "product_price": product['extracted_price'],
                                "product_source": product['source'],
                                "failure_reason": "no_immersive_url",
                                "failure_description": "Produto não possui URL da Immersive API"
                            })
                            product_validations.append(ProductValidation(
                                product_title=product['title'][:60],
                                product_price=product['extracted_price'],
                                product_source=product['source'],
                                iteration=iteration,
                                block_index=0,
                                step=validation_step,
                                immersive_called=False,
                                stores_returned=0,
                                validations=[{"check": "has_immersive_url", "passed": False, "reason": "URL nao disponivel"}],
                                final_status="FAILED",
                                failure_reason="no_immersive_url",
                                selected_store=None
                            ))
                            continue

                        # Chamar Immersive API
                        immersive_url = product['serpapi_immersive_url']
                        if '?' in immersive_url:
                            immersive_url += f"&api_key={serpapi_key}"
                        else:
                            immersive_url += f"?api_key={serpapi_key}"

                        validations_list = []
                        stores_list = []
                        selected_store = None
                        api_error = None

                        try:
                            response = await client.get(immersive_url)
                            response.raise_for_status()
                            data = response.json()

                            stores = data.get('product_results', {}).get('sellers', [])
                            if not stores:
                                stores = data.get('sellers_results', {}).get('online_sellers', [])
                            if not stores:
                                stores = data.get('product_results', [])

                            validations_list.append({"check": "immersive_api_call", "passed": True, "stores_found": len(stores)})

                            if not stores:
                                new_failures.append(product_key)
                                block_skipped["no_store_link"] += 1
                                validations_list.append({"check": "has_stores", "passed": False, "reason": "Nenhuma loja retornada"})
                            else:
                                # Processar cada loja
                                for s in stores:
                                    store_name = s.get('name', s.get('source', 'N/A'))
                                    store_link = s.get('link', s.get('url', ''))
                                    store_price = s.get('price', s.get('base_price', 'N/A'))

                                    store_domain = ""
                                    if store_link:
                                        try:
                                            parsed = urlparse(store_link)
                                            store_domain = parsed.netloc.lower()
                                        except:
                                            pass

                                    store_info = {
                                        "name": store_name,
                                        "price": store_price,
                                        "link": store_link,
                                        "domain": store_domain
                                    }

                                    # Validacao 1: Dominio bloqueado
                                    is_blk, blk_reason = is_blocked_domain(store_domain)
                                    if is_blk:
                                        store_info["status"] = "blocked_domain"
                                        store_info["reason"] = blk_reason
                                        stores_list.append(store_info)
                                        continue

                                    # Validacao 2: Dominio estrangeiro
                                    is_fgn, fgn_reason = is_foreign_domain(store_domain)
                                    if is_fgn:
                                        store_info["status"] = "foreign_domain"
                                        store_info["reason"] = fgn_reason
                                        stores_list.append(store_info)
                                        continue

                                    # Validacao 3: URL duplicada (permite produtos diferentes do mesmo domínio)
                                    if store_link in urls_seen:
                                        store_info["status"] = "duplicate_url"
                                        store_info["reason"] = "URL ja usada em outra cotacao"
                                        stores_list.append(store_info)
                                        continue

                                    # Validacao 4: URL de listagem
                                    is_lst, lst_reason = is_listing_url(store_link)
                                    if is_lst:
                                        store_info["status"] = "listing_url"
                                        store_info["reason"] = lst_reason
                                        stores_list.append(store_info)
                                        continue

                                    # Passou em todas as validacoes!
                                    store_info["status"] = "valid"
                                    stores_list.append(store_info)
                                    if selected_store is None:
                                        selected_store = store_info

                                # Registrar resultado das validacoes
                                blocked_count = sum(1 for s in stores_list if s.get("status") == "blocked_domain")
                                foreign_count = sum(1 for s in stores_list if s.get("status") == "foreign_domain")
                                duplicate_url_count = sum(1 for s in stores_list if s.get("status") == "duplicate_url")
                                listing_count = sum(1 for s in stores_list if s.get("status") == "listing_url")
                                valid_count = sum(1 for s in stores_list if s.get("status") == "valid")

                                validations_list.append({"check": "blocked_domain", "blocked": blocked_count})
                                validations_list.append({"check": "foreign_domain", "blocked": foreign_count})
                                validations_list.append({"check": "duplicate_url", "blocked": duplicate_url_count})
                                validations_list.append({"check": "listing_url", "blocked": listing_count})
                                validations_list.append({"check": "valid_stores", "count": valid_count})

                        except Exception as e:
                            api_error = str(e)[:100]
                            validations_list.append({"check": "immersive_api_call", "passed": False, "error": api_error})
                            new_failures.append(product_key)
                            block_skipped["api_error"] += 1

                        # Registrar resultado do produto
                        if selected_store:
                            urls_seen.add(selected_store['link'])  # URL única, não domínio
                            result_entry = {
                                "title": product['title'],
                                "google_price": product['extracted_price'],
                                "store": selected_store['name'],
                                "store_price": selected_store['price'],
                                "store_link": selected_store['link'],
                                "store_domain": selected_store['domain']
                            }
                            final_results.append(result_entry)
                            results_by_key[product_key] = result_entry
                            block_results_count += 1

                            product_validations.append(ProductValidation(
                                product_title=product['title'][:60],
                                product_price=product['extracted_price'],
                                product_source=product['source'],
                                iteration=iteration,
                                block_index=0,
                                step=validation_step,
                                immersive_called=True,
                                stores_returned=len(stores_list),
                                validations=validations_list,
                                final_status="SUCCESS",
                                failure_reason=None,
                                selected_store=selected_store
                            ))

                            immersive_results.append(ImmersiveResult(
                                product_title=product['title'][:60],
                                source=product['source'],
                                google_price=product['extracted_price'],
                                immersive_url=immersive_url.split('api_key=')[0] + "api_key=***",
                                stores_found=len(stores_list),
                                stores=stores_list[:10],
                                selected_store=selected_store,
                                success=True,
                                error=None
                            ))
                        else:
                            # Falha - nenhuma loja valida
                            if not api_error:
                                new_failures.append(product_key)
                                # Usar variaveis locais se definidas, senao usar 0
                                _blocked = locals().get('blocked_count', 0)
                                _foreign = locals().get('foreign_count', 0)
                                _duplicate_url = locals().get('duplicate_url_count', 0)
                                _listing = locals().get('listing_count', 0)

                                # Determinar motivo específico da falha
                                if _blocked > 0:
                                    block_skipped["blocked_domain"] += 1
                                    fail_reason = "blocked_domain"
                                    fail_desc = f"Todas as {len(stores_list)} lojas estão em domínios bloqueados"
                                elif _foreign > 0:
                                    block_skipped["foreign_domain"] += 1
                                    fail_reason = "foreign_domain"
                                    fail_desc = f"Todas as {len(stores_list)} lojas são de domínios estrangeiros"
                                elif _duplicate_url > 0:
                                    block_skipped["duplicate_url"] += 1
                                    fail_reason = "duplicate_url"
                                    fail_desc = f"Todas as {len(stores_list)} URLs já foram usadas em outras cotações"
                                elif _listing > 0:
                                    block_skipped["listing_url"] += 1
                                    fail_reason = "listing_url"
                                    fail_desc = f"Todas as {len(stores_list)} URLs são páginas de listagem"
                                else:
                                    block_skipped["no_store_link"] += 1
                                    fail_reason = "no_store_link"
                                    fail_desc = "Nenhuma loja válida encontrada na Immersive API"

                                failed_products_details.append({
                                    "product_title": product['title'][:60],
                                    "product_price": product['extracted_price'],
                                    "product_source": product['source'],
                                    "failure_reason": fail_reason,
                                    "failure_description": fail_desc,
                                    "stores_checked": len(stores_list),
                                    "stores_details": [
                                        {"name": s.get("name"), "domain": s.get("domain"), "status": s.get("status"), "reason": s.get("reason")}
                                        for s in stores_list[:5]  # Primeiras 5 lojas
                                    ]
                                })
                            else:
                                # Erro de API
                                failed_products_details.append({
                                    "product_title": product['title'][:60],
                                    "product_price": product['extracted_price'],
                                    "product_source": product['source'],
                                    "failure_reason": "api_error",
                                    "failure_description": f"Erro ao chamar Immersive API: {api_error}"
                                })

                            failure_reason = api_error or "no_valid_store"
                            product_validations.append(ProductValidation(
                                product_title=product['title'][:60],
                                product_price=product['extracted_price'],
                                product_source=product['source'],
                                iteration=iteration,
                                block_index=0,
                                step=validation_step,
                                immersive_called=True,
                                stores_returned=len(stores_list),
                                validations=validations_list,
                                final_status="FAILED",
                                failure_reason=failure_reason,
                                selected_store=None
                            ))

                            immersive_results.append(ImmersiveResult(
                                product_title=product['title'][:60],
                                source=product['source'],
                                google_price=product['extracted_price'],
                                immersive_url=immersive_url.split('api_key=')[0] + "api_key=***",
                                stores_found=len(stores_list),
                                stores=stores_list[:10],
                                selected_store=None,
                                success=False,
                                error=failure_reason
                            ))

                    # Atualizar falhas
                    failed_product_keys.update(new_failures)

                    # Determinar status e acao
                    if len(final_results) >= limit:
                        status = "SUCCESS"
                        action = "completed"
                        block_failure_reason = None
                    elif new_failures:
                        status = "CONTINUING"
                        action = "recreating_blocks"
                        # Determinar motivo da falha do bloco
                        failure_counts = {k: v for k, v in block_skipped.items() if v > 0}
                        if failure_counts:
                            main_reason = max(failure_counts, key=failure_counts.get)
                            block_failure_reason = f"Bloco falhou parcialmente: {len(new_failures)} produtos falharam. Principal motivo: {main_reason} ({failure_counts[main_reason]}x)"
                        else:
                            block_failure_reason = f"Bloco falhou parcialmente: {len(new_failures)} produtos falharam"
                    else:
                        status = "FAILED"
                        action = "no_progress"
                        already_processed = len([p for p in block if f"{p['title']}_{p['extracted_price']}" in failed_product_keys])
                        block_failure_reason = f"Bloco travou: nenhum produto processável restante. Produtos no bloco: {len(block)}, já processados: {already_processed}"

                    block_iterations.append(BlockIteration(
                        iteration=iteration,
                        block_size=len(block),
                        block_min_price=block_min_price,
                        block_max_price=block_max_price,
                        products_processed=len([p for p in block if f"{p['title']}_{p['extracted_price']}" not in failed_product_keys or f"{p['title']}_{p['extracted_price']}" in new_failures]),
                        results_obtained=block_results_count,
                        results_total=len(final_results),
                        failures_in_iteration=len(new_failures),
                        total_failures=len(failed_product_keys),
                        skipped_reasons=block_skipped,
                        status=status,
                        action=action,
                        block_failure_reason=block_failure_reason,
                        failed_products_details=failed_products_details
                    ))

                    if status == "SUCCESS" or action == "no_progress":
                        break

            # Adicionar step 6 com resumo
            steps.append(StepResult(
                step_number=6,
                step_name="Processamento Iterativo com Immersive API",
                description="Validacoes detalhadas e recriacao de blocos em caso de falha (URL unica)",
                input_count=len(products_step4),
                output_count=len(final_results),
                filtered_count=len(failed_product_keys),
                details={
                    "total_iterations": len(block_iterations),
                    "total_validations": len(product_validations),
                    "api_calls_made": len(immersive_results),
                    "successful_quotes": len(final_results),
                    "failed_products": len(failed_product_keys),
                    "urls_used": list(urls_seen),
                    "final_status": "SUCCESS" if len(final_results) >= limit else "PARTIAL"
                }
            ))

        # ============================================
        # Montar resposta final
        # ============================================
        summary = {
            "total_raw_products": len(raw_products),
            "after_source_filter": len(products_step2),
            "after_price_filter": len(products_step3),
            "after_limit": len(products_step4),
            "total_blocks": len(blocks),
            "valid_blocks": len(valid_blocks),
            "quotes_target": limit,
            "quotes_obtained": len(final_results),
            "variacao_maxima": f"{variacao_maxima}%",
            "immersive_executed": execute_immersive,
            "total_iterations": len(block_iterations) if execute_immersive else 0,
            "total_product_validations": len(product_validations) if execute_immersive else 0
        }

        return DebugResponse(
            success=True,
            query=query,
            parameters={
                "limit": limit,
                "variacao_maxima": variacao_maxima,
                "execute_immersive": execute_immersive
            },
            steps=steps,
            blocks=valid_blocks[:10],  # Top 10 blocos
            immersive_results=immersive_results,
            product_validations=product_validations,
            block_iterations=block_iterations,
            final_results=final_results,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no debug SerpAPI: {e}")
        import traceback
        traceback.print_exc()
        return DebugResponse(
            success=False,
            query="",
            parameters={},
            steps=[],
            blocks=[],
            immersive_results=[],
            product_validations=[],
            block_iterations=[],
            final_results=[],
            summary={},
            error=str(e)
        )
