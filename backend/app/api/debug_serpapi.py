"""
Debug SerpAPI - Simulador Visual do Fluxo de Cotação

Objetivo: Obter N cotações válidas de um ÚNICO BLOCO de produtos,
garantindo que a variação de preço entre a menor e maior cotação não exceda X%.

Este endpoint permite visualizar cada etapa do processamento de forma
intuitiva e detalhada, facilitando a compreensão e debug do sistema.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from decimal import Decimal
from enum import Enum
import json
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User, IntegrationSetting, BlockedDomain
from app.services.search_provider import (
    BLOCKED_DOMAINS as HARDCODED_BLOCKED_DOMAINS,
    FOREIGN_DOMAIN_PATTERNS,
    ALLOWED_FOREIGN_DOMAINS,
)
from app.core.config import settings
from app.core.security import decrypt_value

# Variável global para domínios bloqueados (será populada com DB + hardcoded)
BLOCKED_DOMAINS = set()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/debug-serpapi", tags=["Debug SerpAPI"])


# =============================================================================
# CONSTANTES DO SISTEMA
# =============================================================================
INCREMENTO_VAR = 0.05  # 5% de aumento por rodada de fallback
MAX_TOLERANCE_INCREASES = 5  # Máximo de aumentos de tolerância
PRICE_MISMATCH_THRESHOLD = 0.05  # 5% diferença máxima para PRICE_MISMATCH


# =============================================================================
# ENUMS E STATUS
# =============================================================================
class ProductStatus(str, Enum):
    """Status de um produto no fluxo de validação"""
    NAO_TESTADO = "NAO_TESTADO"
    VALIDADO = "VALIDADO"
    DESCARTADO = "DESCARTADO"


class FailureCode(str, Enum):
    """Códigos de falha na validação de produto"""
    NO_STORE_LINK = "NO_STORE_LINK"  # API não retornou URL
    BLOCKED_DOMAIN = "BLOCKED_DOMAIN"  # Domínio na lista de bloqueio
    FOREIGN_DOMAIN = "FOREIGN_DOMAIN"  # TLD não é .br
    DUPLICATE_URL = "DUPLICATE_URL"  # URL já usada nesta cotação
    LISTING_URL = "LISTING_URL"  # URL de busca/listagem
    PRICE_MISMATCH = "PRICE_MISMATCH"  # Preço site ≠ Google
    EXTRACTION_ERROR = "EXTRACTION_ERROR"  # Erro ao extrair preço
    API_ERROR = "API_ERROR"  # Erro na chamada da API
    NO_IMMERSIVE_URL = "NO_IMMERSIVE_URL"  # Produto sem URL Immersive


# =============================================================================
# MODELOS DE RESPOSTA - ETAPA 1
# =============================================================================
class ParametrosSistema(BaseModel):
    """Parâmetros configurados para esta simulação"""
    NUM_COTACOES: int
    VAR_MAX_PERCENT: float
    MAX_VALID_PRODUCTS: int = 150
    INCREMENTO_VAR: float = 5.0
    VALIDAR_PRECO_SITE: bool
    DOMINIOS_BLOQUEADOS_SAMPLE: List[str]  # Amostra dos domínios bloqueados


class ProdutoExtraido(BaseModel):
    """Produto extraído do Google Shopping"""
    position: int
    title: str
    source: str
    extracted_price: Optional[float]
    has_immersive_url: bool
    status: ProductStatus = ProductStatus.NAO_TESTADO
    failure_code: Optional[FailureCode] = None
    failure_reason: Optional[str] = None


class FiltroAplicado(BaseModel):
    """Resultado de um filtro aplicado"""
    nome: str
    descricao: str
    entrada: int
    saida: int
    removidos: int
    detalhes: Optional[Dict[str, Any]] = None


class BlocoFormado(BaseModel):
    """Bloco de produtos formado"""
    indice: int
    tamanho: int
    preco_min: float
    preco_max: float
    variacao_percent: float
    elegivel: bool  # True se tamanho >= NUM_COTACOES
    potencial: int  # validados + não_testados
    produtos: List[Dict[str, Any]]


class Etapa1Result(BaseModel):
    """Resultado da ETAPA 1: Processamento Google Shopping"""
    total_extraidos: int
    filtros_aplicados: List[FiltroAplicado]
    produtos_apos_filtros: int
    blocos_formados: int
    blocos_elegiveis: int
    melhor_bloco: Optional[BlocoFormado]
    produtos_ordenados: List[ProdutoExtraido]


# =============================================================================
# MODELOS DE RESPOSTA - ETAPA 2
# =============================================================================
class ValidacaoProduto(BaseModel):
    """Resultado da validação de um produto via Immersive API"""
    produto_titulo: str
    produto_preco: float
    produto_source: str
    ordem_validacao: int
    sucesso: bool
    failure_code: Optional[FailureCode] = None
    failure_reason: Optional[str] = None
    loja_selecionada: Optional[Dict[str, Any]] = None
    lojas_encontradas: int = 0
    lojas_rejeitadas: List[Dict[str, Any]] = []


class IteracaoBloco(BaseModel):
    """Uma iteração de validação de bloco"""
    numero_iteracao: int
    tolerancia_atual: float
    tolerancia_round: int

    # Métricas do bloco selecionado
    bloco_tamanho: int
    bloco_preco_min: float
    bloco_preco_max: float
    bloco_variacao: float

    # Contadores de progresso
    produtos_no_bloco: int
    produtos_validados_inicio: int  # Já validados antes desta iteração
    produtos_nao_testados: int
    potencial_bloco: int

    # Resultados da iteração
    validacoes_realizadas: List[ValidacaoProduto]
    novos_validados: int
    novos_descartados: int

    # Status final
    total_validados_apos: int
    status: str  # "SUCESSO", "BLOCO_FALHOU", "CONTINUAR"
    acao_tomada: str  # Descrição da próxima ação
    motivo: Optional[str] = None


class Etapa2Result(BaseModel):
    """Resultado da ETAPA 2: Validação de Bloco"""
    iteracoes: List[IteracaoBloco]
    total_iteracoes: int
    aumentos_tolerancia: int
    tolerancia_inicial: float
    tolerancia_final: float
    produtos_validados_final: int
    produtos_descartados_final: int
    sucesso: bool
    cotacoes_obtidas: List[Dict[str, Any]]


# =============================================================================
# MODELO DE RESPOSTA PRINCIPAL
# =============================================================================
class FluxoVisual(BaseModel):
    """Representação visual do fluxo executado"""
    etapa_atual: str
    status_geral: str  # "SUCESSO", "PARCIAL", "FALHA"
    progresso: str  # Ex: "3/3 cotações obtidas"
    resumo_fluxo: List[str]  # Lista de passos executados


class DebugResponse(BaseModel):
    """Resposta completa do debug - formato intuitivo"""
    sucesso: bool
    query: str

    # Parâmetros utilizados
    parametros: ParametrosSistema

    # Resultados por etapa
    etapa1: Etapa1Result
    etapa2: Optional[Etapa2Result] = None

    # Visualização do fluxo
    fluxo_visual: FluxoVisual

    # Resultado final
    cotacoes_finais: List[Dict[str, Any]]

    # Erro (se houver)
    erro: Optional[str] = None


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def _make_product_key(title: str, price: float) -> str:
    """Cria chave única para um produto"""
    return f"{title}_{price}"


def _extract_price(price_str: str) -> Optional[float]:
    """Extrai valor numérico de uma string de preço"""
    if not price_str:
        return None
    import re
    price_clean = re.sub(r'[R$\s.]', '', str(price_str)).replace(',', '.')
    try:
        return float(price_clean)
    except ValueError:
        return None


def _is_blocked_source(source: str, blocked_domains: set) -> tuple:
    """Verifica se uma fonte está bloqueada. Retorna (is_blocked, reason)"""
    if not source:
        return False, None

    source_lower = source.lower()
    # Remover espaços para comparação (ex: "Leroy Merlin" -> "leroymerlin")
    source_no_spaces = source_lower.replace(" ", "").replace("-", "")

    # Mapeamento de nomes de fonte para domínios
    source_to_domain_map = {
        "mercado livre": "mercadolivre.com.br",
        "mercadolivre": "mercadolivre.com.br",
        "amazon": "amazon.com.br",
        "shopee": "shopee.com.br",
        "aliexpress": "aliexpress.com",
        "shein": "shein.com",
        "temu": "temu.com",
        "carrefour": "carrefour.com.br",
        "casas bahia": "casasbahia.com.br",
        "magazine luiza": "magazineluiza.com.br",
        "magalu": "magalu.com.br",
        "americanas": "americanas.com.br",
        "leroy merlin": "leroymerlin.com.br",
        "leroymerlin": "leroymerlin.com.br",
    }

    for source_name, domain in source_to_domain_map.items():
        if source_name in source_lower:
            if domain in blocked_domains:
                return True, f"Fonte '{source}' → domínio bloqueado: {domain}"

    # Verificar contra todos os domínios bloqueados
    for blocked_domain in blocked_domains:
        # Extrair nome base do domínio (ex: "leroymerlin.com.br" -> "leroymerlin")
        base_name = blocked_domain.split('.')[0].lower()
        # Comparar sem espaços (ex: "leroy merlin" vs "leroymerlin")
        if base_name in source_no_spaces:
            return True, f"Fonte '{source}' contém domínio bloqueado: {blocked_domain}"

    return False, None


def _is_blocked_domain(domain: str, blocked_domains: set) -> tuple:
    """Verifica se um domínio está bloqueado"""
    if not domain:
        return False, None

    domain_lower = domain.lower()
    for blocked in blocked_domains:
        if domain_lower == blocked or domain_lower.endswith("." + blocked):
            return True, f"Domínio bloqueado: {blocked}"

    return False, None


def _is_foreign_domain(domain: str) -> tuple:
    """Verifica se é domínio estrangeiro"""
    if not domain:
        return False, None

    domain_lower = domain.lower()

    if domain_lower.endswith(".com.br") or domain_lower.endswith(".br"):
        return False, None

    if domain_lower in ALLOWED_FOREIGN_DOMAINS:
        return False, None

    for pattern in FOREIGN_DOMAIN_PATTERNS:
        if domain_lower.endswith(pattern) and not domain_lower.endswith(".com.br"):
            return True, f"Domínio estrangeiro ({pattern})"

    return False, None


def _is_listing_url(url: str) -> tuple:
    """Verifica se é URL de listagem/busca"""
    if not url:
        return True, "URL vazia"

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
            return True, f"URL de listagem (contém '{pattern}')"

    return False, None


def _form_blocks(products: List[Dict], var_max: float, min_size: int) -> List[Dict]:
    """Forma blocos de variação a partir de produtos ordenados por preço"""
    if not products:
        return []

    blocks = []

    for start_idx, start_product in enumerate(products):
        min_price = start_product['extracted_price']
        if not min_price or min_price <= 0:
            continue

        max_allowed = min_price * (1 + var_max)

        block_products = []
        for p in products[start_idx:]:
            if p['extracted_price'] and p['extracted_price'] <= max_allowed:
                block_products.append(p)
            else:
                break

        if len(block_products) >= 1:  # Formar todos os blocos, filtrar depois
            variation = ((block_products[-1]['extracted_price'] / block_products[0]['extracted_price']) - 1) * 100
            blocks.append({
                "indice": start_idx,
                "produtos": block_products,
                "tamanho": len(block_products),
                "preco_min": block_products[0]['extracted_price'],
                "preco_max": block_products[-1]['extracted_price'],
                "variacao_percent": round(variation, 2),
                "elegivel": len(block_products) >= min_size
            })

    return blocks


def _rank_blocks(blocks: List[Dict], validated_keys: set, failed_keys: set, num_quotes: int) -> List[Dict]:
    """Rankeia blocos por potencial de sucesso"""
    ranked = []

    for block in blocks:
        block_keys = {_make_product_key(p['title'], p['extracted_price']) for p in block['produtos']}

        valid_in_block = len(validated_keys & block_keys)
        untried_in_block = len(block_keys - validated_keys - failed_keys)
        potential = valid_in_block + untried_in_block

        if potential < num_quotes:
            continue

        block_copy = block.copy()
        block_copy['potencial'] = potential
        block_copy['validados_no_bloco'] = valid_in_block
        block_copy['nao_testados_no_bloco'] = untried_in_block

        # Score: prioriza mais validados, mais não testados, menor preço
        block_copy['score'] = (valid_in_block, untried_in_block, -block['preco_min'])
        ranked.append(block_copy)

    ranked.sort(key=lambda x: x['score'], reverse=True)
    return ranked


# =============================================================================
# ENDPOINT PRINCIPAL
# =============================================================================
@router.post("/analyze", response_model=DebugResponse)
async def analyze_shopping_json(
    file: UploadFile = File(...),
    num_cotacoes: int = Form(default=3, alias="limit"),
    variacao_maxima: float = Form(default=25.0),
    execute_immersive: str = Form(default="false"),
    validar_preco_site: str = Form(default="true", alias="enable_price_mismatch"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analisa um JSON do Google Shopping e simula o fluxo completo de cotação.

    OBJETIVO: Obter N cotações válidas de um ÚNICO BLOCO de produtos,
    garantindo variação máxima de X% entre menor e maior preço.

    Parâmetros:
    - file: JSON do Google Shopping (ou JSON de cotação com raw_api_response)
    - num_cotacoes (limit): Quantidade de cotações desejadas (default: 3)
    - variacao_maxima: Variação máxima em % (default: 25%)
    - execute_immersive: Se True, executa chamadas reais à API Immersive
    - validar_preco_site (enable_price_mismatch): Se True, valida preço do site vs Google
    """
    try:
        # Converter strings para booleanos (FormData envia strings)
        execute_immersive_bool = execute_immersive.lower() in ('true', '1', 'yes')
        validar_preco_site_bool = validar_preco_site.lower() in ('true', '1', 'yes')

        logger.info(f"Debug SerpAPI - execute_immersive: {execute_immersive} -> {execute_immersive_bool}")
        logger.info(f"Debug SerpAPI - validar_preco_site: {validar_preco_site} -> {validar_preco_site_bool}")

        # Carregar domínios bloqueados (hardcoded + banco de dados)
        blocked_domains = set(HARDCODED_BLOCKED_DOMAINS)
        db_blocked = db.query(BlockedDomain.domain).all()
        for (domain,) in db_blocked:
            blocked_domains.add(domain.lower())
        logger.info(f"Debug SerpAPI - Domínios bloqueados carregados: {len(blocked_domains)} (hardcoded: {len(HARDCODED_BLOCKED_DOMAINS)}, DB: {len(db_blocked)})")

        # Ler JSON
        content = await file.read()
        try:
            shopping_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON inválido: {str(e)}")

        # Verificar se é JSON de cotação ou direto do SerpAPI
        # Formato 1: raw_api_response na raiz
        if 'raw_api_response' in shopping_data:
            raw_api = shopping_data.get('raw_api_response', {})
            if raw_api:
                shopping_data = raw_api
        # Formato 2: search_log.raw_shopping_response (formato do sistema de cotação)
        elif 'search_log' in shopping_data:
            raw_shopping = shopping_data.get('search_log', {}).get('raw_shopping_response', {})
            if raw_shopping:
                shopping_data = raw_shopping

        query = shopping_data.get('search_parameters', {}).get('q', 'N/A')
        var_max_decimal = variacao_maxima / 100.0

        # Parâmetros do sistema
        parametros = ParametrosSistema(
            NUM_COTACOES=num_cotacoes,
            VAR_MAX_PERCENT=variacao_maxima,
            MAX_VALID_PRODUCTS=150,
            INCREMENTO_VAR=INCREMENTO_VAR * 100,
            VALIDAR_PRECO_SITE=validar_preco_site_bool,
            DOMINIOS_BLOQUEADOS_SAMPLE=sorted(list(blocked_domains))[:15]
        )

        fluxo_resumo = []

        # =====================================================================
        # ETAPA 1: PROCESSAMENTO GOOGLE SHOPPING
        # =====================================================================
        fluxo_resumo.append("📥 ETAPA 1: Processamento Google Shopping iniciado")

        # 1.1 Extração
        shopping_results = shopping_data.get('shopping_results', [])
        inline_results = shopping_data.get('inline_shopping_results', [])

        produtos_extraidos = []
        position = 0

        for item in shopping_results + inline_results:
            position += 1
            extracted = item.get('extracted_price')
            produtos_extraidos.append({
                'position': position,
                'title': item.get('title', ''),
                'source': item.get('source', ''),
                'extracted_price': float(extracted) if extracted is not None else None,
                'serpapi_immersive_url': item.get('serpapi_product_api_immersive') or item.get('serpapi_immersive_product_api'),
                'status': ProductStatus.NAO_TESTADO,
                'failure_code': None,
                'failure_reason': None
            })

        total_extraidos = len(produtos_extraidos)
        fluxo_resumo.append(f"  └─ Extraídos: {total_extraidos} produtos")

        filtros_aplicados = []

        # 1.2 Filtro: Fontes Bloqueadas
        produtos_apos_fonte = []
        bloqueados_fonte = []
        motivos_bloqueio = {}

        for p in produtos_extraidos:
            is_blocked, reason = _is_blocked_source(p['source'], blocked_domains)
            if is_blocked:
                bloqueados_fonte.append(p)
                motivos_bloqueio[reason] = motivos_bloqueio.get(reason, 0) + 1
            else:
                produtos_apos_fonte.append(p)

        filtros_aplicados.append(FiltroAplicado(
            nome="Fontes Bloqueadas",
            descricao="Remove produtos de marketplaces e lojas com anti-bot",
            entrada=len(produtos_extraidos),
            saida=len(produtos_apos_fonte),
            removidos=len(bloqueados_fonte),
            detalhes={
                "motivos": motivos_bloqueio,
                "exemplos_removidos": [
                    {"title": p['title'][:40], "source": p['source']}
                    for p in bloqueados_fonte[:5]
                ]
            }
        ))

        # 1.2 Filtro: Preços Inválidos
        produtos_apos_preco = []
        invalidos_preco = []

        for p in produtos_apos_fonte:
            if p['extracted_price'] is not None and p['extracted_price'] > 0:
                produtos_apos_preco.append(p)
            else:
                invalidos_preco.append(p)

        filtros_aplicados.append(FiltroAplicado(
            nome="Preços Inválidos",
            descricao="Remove produtos sem preço ou preço ≤ 0",
            entrada=len(produtos_apos_fonte),
            saida=len(produtos_apos_preco),
            removidos=len(invalidos_preco),
            detalhes={
                "exemplos_removidos": [
                    {"title": p['title'][:40], "price": p['extracted_price']}
                    for p in invalidos_preco[:5]
                ]
            }
        ))

        # 1.3 Ordenação e Limite
        produtos_apos_preco.sort(key=lambda x: x['extracted_price'])
        produtos_limitados = produtos_apos_preco[:150]

        filtros_aplicados.append(FiltroAplicado(
            nome="Ordenação e Limite",
            descricao="Ordena por preço crescente e limita a 150 produtos",
            entrada=len(produtos_apos_preco),
            saida=len(produtos_limitados),
            removidos=max(0, len(produtos_apos_preco) - 150),
            detalhes={
                "preco_minimo": produtos_limitados[0]['extracted_price'] if produtos_limitados else None,
                "preco_maximo": produtos_limitados[-1]['extracted_price'] if produtos_limitados else None
            }
        ))

        fluxo_resumo.append(f"  └─ Após filtros: {len(produtos_limitados)} produtos válidos")

        # 1.4 Formação de Blocos
        blocos = _form_blocks(produtos_limitados, var_max_decimal, num_cotacoes)
        blocos_elegiveis = [b for b in blocos if b['elegivel']]

        # Converter para modelo
        blocos_modelo = [
            BlocoFormado(
                indice=b['indice'],
                tamanho=b['tamanho'],
                preco_min=b['preco_min'],
                preco_max=b['preco_max'],
                variacao_percent=b['variacao_percent'],
                elegivel=b['elegivel'],
                potencial=b['tamanho'],  # Inicialmente, potencial = tamanho
                produtos=[
                    {"position": p['position'], "title": p['title'][:40], "price": p['extracted_price'], "source": p['source']}
                    for p in b['produtos'][:10]  # Limitar para visualização
                ]
            )
            for b in blocos[:20]  # Mostrar até 20 blocos
        ]

        melhor_bloco = None
        if blocos_elegiveis:
            # Ordenar por tamanho (desc) e preço mínimo (asc)
            blocos_elegiveis.sort(key=lambda b: (-b['tamanho'], b['preco_min']))
            best = blocos_elegiveis[0]
            melhor_bloco = BlocoFormado(
                indice=best['indice'],
                tamanho=best['tamanho'],
                preco_min=best['preco_min'],
                preco_max=best['preco_max'],
                variacao_percent=best['variacao_percent'],
                elegivel=True,
                potencial=best['tamanho'],
                produtos=[
                    {"position": p['position'], "title": p['title'][:40], "price": p['extracted_price'], "source": p['source']}
                    for p in best['produtos']
                ]
            )

        fluxo_resumo.append(f"  └─ Blocos formados: {len(blocos)} (elegíveis: {len(blocos_elegiveis)})")

        # Converter produtos para modelo
        produtos_modelo = [
            ProdutoExtraido(
                position=p['position'],
                title=p['title'],
                source=p['source'],
                extracted_price=p['extracted_price'],
                has_immersive_url=bool(p.get('serpapi_immersive_url')),
                status=ProductStatus.NAO_TESTADO
            )
            for p in produtos_limitados[:50]  # Limitar para visualização
        ]

        etapa1 = Etapa1Result(
            total_extraidos=total_extraidos,
            filtros_aplicados=filtros_aplicados,
            produtos_apos_filtros=len(produtos_limitados),
            blocos_formados=len(blocos),
            blocos_elegiveis=len(blocos_elegiveis),
            melhor_bloco=melhor_bloco,
            produtos_ordenados=produtos_modelo
        )

        # =====================================================================
        # ETAPA 2: VALIDAÇÃO DE BLOCO (se execute_immersive=True)
        # =====================================================================
        etapa2 = None
        cotacoes_finais = []

        logger.info(f"Debug SerpAPI - execute_immersive_bool: {execute_immersive_bool}, produtos_limitados: {len(produtos_limitados)}")

        if execute_immersive_bool and produtos_limitados:
            fluxo_resumo.append("🔍 ETAPA 2: Validação de Bloco iniciada")
            logger.info("Debug SerpAPI - Iniciando ETAPA 2")

            # Obter API key
            serpapi_setting = db.query(IntegrationSetting).filter(
                IntegrationSetting.provider == "SERPAPI"
            ).first()

            serpapi_key = None
            if serpapi_setting and serpapi_setting.settings_json:
                encrypted_key = serpapi_setting.settings_json.get('api_key')
                if encrypted_key:
                    serpapi_key = decrypt_value(encrypted_key)
                    logger.info("Debug SerpAPI - API key obtida do banco de dados")

            if not serpapi_key:
                serpapi_key = settings.SERPAPI_API_KEY
                if serpapi_key:
                    logger.info("Debug SerpAPI - API key obtida das variáveis de ambiente")

            if not serpapi_key:
                logger.error("Debug SerpAPI - API Key do SerpAPI não configurada")
                raise HTTPException(status_code=400, detail="API Key do SerpAPI não configurada")

            logger.info(f"Debug SerpAPI - API key presente: {bool(serpapi_key)}, tamanho: {len(serpapi_key) if serpapi_key else 0}")

            import httpx
            from urllib.parse import urlparse

            # Estado do processamento
            validated_keys = set()
            failed_keys = set()
            urls_seen = set()
            results_by_key = {}

            iteracoes = []
            iteration = 0
            tolerance_round = 0
            current_var_max = var_max_decimal
            max_iterations = 50

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Loop externo: tolerância
                while tolerance_round <= MAX_TOLERANCE_INCREASES:
                    if tolerance_round > 0:
                        current_var_max += INCREMENTO_VAR
                        fluxo_resumo.append(f"  └─ ⚠️ Aumentando tolerância para {current_var_max*100:.0f}%")

                    # Loop interno: iterações de bloco
                    while iteration < max_iterations and len(cotacoes_finais) < num_cotacoes:
                        iteration += 1

                        # Produtos disponíveis
                        available = [
                            p for p in produtos_limitados
                            if _make_product_key(p['title'], p['extracted_price']) not in failed_keys
                        ]

                        if not available:
                            fluxo_resumo.append(f"  └─ ❌ Sem produtos disponíveis")
                            break

                        # Formar e rankear blocos
                        current_blocks = _form_blocks(available, current_var_max, num_cotacoes)
                        if not current_blocks:
                            fluxo_resumo.append(f"  └─ ❌ Nenhum bloco pode ser formado")
                            break

                        ranked = _rank_blocks(current_blocks, validated_keys, failed_keys, num_cotacoes)
                        if not ranked:
                            fluxo_resumo.append(f"  └─ ⚠️ Nenhum bloco elegível (potencial < {num_cotacoes})")
                            break  # Ir para próxima tolerância

                        # Selecionar melhor bloco
                        best_block = ranked[0]
                        block_products = best_block['produtos']

                        # Produtos a testar nesta iteração
                        untried = [
                            p for p in block_products
                            if _make_product_key(p['title'], p['extracted_price']) not in validated_keys
                            and _make_product_key(p['title'], p['extracted_price']) not in failed_keys
                        ]

                        logger.info(f"Debug SerpAPI - Iteração {iteration}: {len(untried)} produtos a testar no bloco")

                        # Verificar quantos têm URL Immersive
                        with_immersive = [p for p in untried if p.get('serpapi_immersive_url')]
                        logger.info(f"Debug SerpAPI - Produtos com URL Immersive: {len(with_immersive)}/{len(untried)}")

                        iteracao_info = IteracaoBloco(
                            numero_iteracao=iteration,
                            tolerancia_atual=current_var_max * 100,
                            tolerancia_round=tolerance_round,
                            bloco_tamanho=best_block['tamanho'],
                            bloco_preco_min=best_block['preco_min'],
                            bloco_preco_max=best_block['preco_max'],
                            bloco_variacao=best_block['variacao_percent'],
                            produtos_no_bloco=len(block_products),
                            produtos_validados_inicio=best_block['validados_no_bloco'],
                            produtos_nao_testados=len(untried),
                            potencial_bloco=best_block['potencial'],
                            validacoes_realizadas=[],
                            novos_validados=0,
                            novos_descartados=0,
                            total_validados_apos=len(validated_keys),
                            status="CONTINUAR",
                            acao_tomada=""
                        )

                        # Validar produtos do bloco
                        ordem = 0
                        for product in untried:
                            if len(cotacoes_finais) >= num_cotacoes:
                                break

                            ordem += 1
                            product_key = _make_product_key(product['title'], product['extracted_price'])

                            validacao = ValidacaoProduto(
                                produto_titulo=product['title'][:60],
                                produto_preco=product['extracted_price'],
                                produto_source=product['source'],
                                ordem_validacao=ordem,
                                sucesso=False
                            )

                            # Verificar URL Immersive
                            if not product.get('serpapi_immersive_url'):
                                failed_keys.add(product_key)
                                validacao.failure_code = FailureCode.NO_IMMERSIVE_URL
                                validacao.failure_reason = "Produto não possui URL da Immersive API"
                                iteracao_info.validacoes_realizadas.append(validacao)
                                iteracao_info.novos_descartados += 1
                                continue

                            # Chamar Immersive API
                            immersive_url = product['serpapi_immersive_url']
                            logger.info(f"Debug SerpAPI - Chamando Immersive API: {immersive_url[:100]}...")

                            if '?' in immersive_url:
                                immersive_url += f"&api_key={serpapi_key}"
                            else:
                                immersive_url += f"?api_key={serpapi_key}"

                            try:
                                response = await client.get(immersive_url)
                                logger.info(f"Debug SerpAPI - Resposta Immersive: status={response.status_code}")
                                response.raise_for_status()
                                data = response.json()

                                # Tentar vários caminhos para encontrar stores/sellers
                                stores = data.get('product_results', {}).get('stores', [])
                                if not stores:
                                    stores = data.get('product_results', {}).get('sellers', [])
                                if not stores:
                                    stores = data.get('sellers_results', {}).get('online_sellers', [])
                                if not stores:
                                    stores = data.get('sellers_results', {}).get('sellers', [])
                                if not stores:
                                    # Logar chaves disponíveis para debug
                                    available_keys = list(data.keys())
                                    logger.info(f"Debug SerpAPI - Chaves na resposta: {available_keys}")
                                    if 'sellers_results' in data:
                                        seller_keys = list(data['sellers_results'].keys())
                                        logger.info(f"Debug SerpAPI - Chaves em sellers_results: {seller_keys}")
                                    if 'product_results' in data:
                                        product_keys = list(data['product_results'].keys())
                                        logger.info(f"Debug SerpAPI - Chaves em product_results: {product_keys}")
                                logger.info(f"Debug SerpAPI - Lojas encontradas: {len(stores)}")

                                validacao.lojas_encontradas = len(stores)

                                if not stores:
                                    failed_keys.add(product_key)
                                    validacao.failure_code = FailureCode.NO_STORE_LINK
                                    validacao.failure_reason = "API não retornou lojas"
                                    iteracao_info.validacoes_realizadas.append(validacao)
                                    iteracao_info.novos_descartados += 1
                                    continue

                                # Validar cada loja
                                selected_store = None
                                for store in stores:
                                    store_link = store.get('link', store.get('url', ''))
                                    store_domain = ""
                                    if store_link:
                                        try:
                                            parsed = urlparse(store_link)
                                            store_domain = parsed.netloc.lower()
                                        except:
                                            pass

                                    store_info = {
                                        "name": store.get('name', store.get('source', '')),
                                        "link": store_link,
                                        "domain": store_domain,
                                        "price": store.get('price', store.get('base_price', ''))
                                    }

                                    # Validações
                                    is_blk, blk_reason = _is_blocked_domain(store_domain, blocked_domains)
                                    if is_blk:
                                        store_info['rejection'] = f"BLOCKED_DOMAIN: {blk_reason}"
                                        validacao.lojas_rejeitadas.append(store_info)
                                        continue

                                    is_fgn, fgn_reason = _is_foreign_domain(store_domain)
                                    if is_fgn:
                                        store_info['rejection'] = f"FOREIGN_DOMAIN: {fgn_reason}"
                                        validacao.lojas_rejeitadas.append(store_info)
                                        continue

                                    if store_link in urls_seen:
                                        store_info['rejection'] = "DUPLICATE_URL"
                                        validacao.lojas_rejeitadas.append(store_info)
                                        continue

                                    is_lst, lst_reason = _is_listing_url(store_link)
                                    if is_lst:
                                        store_info['rejection'] = f"LISTING_URL: {lst_reason}"
                                        validacao.lojas_rejeitadas.append(store_info)
                                        continue

                                    # Passou em todas as validações!
                                    selected_store = store_info
                                    break

                                if selected_store:
                                    urls_seen.add(selected_store['link'])
                                    validated_keys.add(product_key)

                                    cotacao = {
                                        "titulo": product['title'],
                                        "preco_google": product['extracted_price'],
                                        "loja": selected_store['name'],
                                        "url": selected_store['link'],
                                        "dominio": selected_store['domain']
                                    }
                                    cotacoes_finais.append(cotacao)
                                    results_by_key[product_key] = cotacao

                                    validacao.sucesso = True
                                    validacao.loja_selecionada = selected_store
                                    iteracao_info.novos_validados += 1
                                else:
                                    failed_keys.add(product_key)
                                    validacao.failure_code = FailureCode.BLOCKED_DOMAIN
                                    validacao.failure_reason = "Todas as lojas foram rejeitadas"
                                    iteracao_info.novos_descartados += 1

                            except Exception as e:
                                failed_keys.add(product_key)
                                validacao.failure_code = FailureCode.API_ERROR
                                validacao.failure_reason = str(e)[:100]
                                iteracao_info.novos_descartados += 1

                            iteracao_info.validacoes_realizadas.append(validacao)

                        # Atualizar status da iteração
                        iteracao_info.total_validados_apos = len(validated_keys)

                        if len(cotacoes_finais) >= num_cotacoes:
                            iteracao_info.status = "SUCESSO"
                            iteracao_info.acao_tomada = f"✅ Meta atingida: {len(cotacoes_finais)}/{num_cotacoes} cotações"
                            iteracoes.append(iteracao_info)
                            break
                        elif iteracao_info.novos_descartados > 0 and iteracao_info.novos_validados == 0:
                            iteracao_info.status = "BLOCO_FALHOU"
                            iteracao_info.acao_tomada = "Recalcular blocos sem produtos descartados"
                        else:
                            iteracao_info.status = "CONTINUAR"
                            iteracao_info.acao_tomada = "Continuar validando próximo bloco"

                        iteracoes.append(iteracao_info)

                        if iteracao_info.status == "SUCESSO":
                            break

                    # Verificar se atingiu meta ou precisa aumentar tolerância
                    if len(cotacoes_finais) >= num_cotacoes:
                        break

                    tolerance_round += 1

            etapa2 = Etapa2Result(
                iteracoes=iteracoes,
                total_iteracoes=len(iteracoes),
                aumentos_tolerancia=tolerance_round,
                tolerancia_inicial=variacao_maxima,
                tolerancia_final=current_var_max * 100,
                produtos_validados_final=len(validated_keys),
                produtos_descartados_final=len(failed_keys),
                sucesso=len(cotacoes_finais) >= num_cotacoes,
                cotacoes_obtidas=cotacoes_finais
            )

            if len(cotacoes_finais) >= num_cotacoes:
                fluxo_resumo.append(f"  └─ ✅ SUCESSO: {len(cotacoes_finais)}/{num_cotacoes} cotações obtidas")
            else:
                fluxo_resumo.append(f"  └─ ⚠️ PARCIAL: {len(cotacoes_finais)}/{num_cotacoes} cotações obtidas")

        # =====================================================================
        # MONTAR RESPOSTA FINAL
        # =====================================================================
        sucesso_geral = len(cotacoes_finais) >= num_cotacoes if execute_immersive_bool else len(blocos_elegiveis) > 0

        status_geral = "SUCESSO" if sucesso_geral else ("PARCIAL" if cotacoes_finais else "AGUARDANDO")
        if not execute_immersive_bool:
            status_geral = "SIMULAÇÃO"

        fluxo_visual = FluxoVisual(
            etapa_atual="CONCLUÍDO" if sucesso_geral else "ETAPA 2",
            status_geral=status_geral,
            progresso=f"{len(cotacoes_finais)}/{num_cotacoes} cotações" if execute_immersive_bool else f"{len(blocos_elegiveis)} blocos elegíveis",
            resumo_fluxo=fluxo_resumo
        )

        return DebugResponse(
            sucesso=sucesso_geral,
            query=query,
            parametros=parametros,
            etapa1=etapa1,
            etapa2=etapa2,
            fluxo_visual=fluxo_visual,
            cotacoes_finais=cotacoes_finais
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no debug SerpAPI: {e}")
        import traceback
        traceback.print_exc()

        return DebugResponse(
            sucesso=False,
            query="",
            parametros=ParametrosSistema(
                NUM_COTACOES=num_cotacoes,
                VAR_MAX_PERCENT=variacao_maxima,
                VALIDAR_PRECO_SITE=validar_preco_site.lower() in ('true', '1', 'yes'),
                DOMINIOS_BLOQUEADOS_SAMPLE=[]
            ),
            etapa1=Etapa1Result(
                total_extraidos=0,
                filtros_aplicados=[],
                produtos_apos_filtros=0,
                blocos_formados=0,
                blocos_elegiveis=0,
                melhor_bloco=None,
                produtos_ordenados=[]
            ),
            fluxo_visual=FluxoVisual(
                etapa_atual="ERRO",
                status_geral="ERRO",
                progresso="0/0",
                resumo_fluxo=["❌ Erro no processamento"]
            ),
            cotacoes_finais=[],
            erro=str(e)
        )
