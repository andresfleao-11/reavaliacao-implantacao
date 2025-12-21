from celery import Task
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import QuoteRequest, QuoteSource, File, GeneratedDocument, IntegrationLog, BlockedDomain, QuoteSourceFailure, CaptureFailureReason
from app.models.quote_request import QuoteStatus, QuoteInputType
from app.services.checkpoint_manager import CheckpointManager, ProcessingCheckpoint
from app.models.file import FileType
from app.models.financial import ApiCostConfig, FinancialTransaction
from app.services.claude_client import ClaudeClient, FipeApiParams
from app.services.openai_client import OpenAIClient
from app.services.search_provider import SerpApiProvider, prices_match, PRICE_MISMATCH_TOLERANCE, ShoppingProduct
from app.services.price_extractor import PriceExtractor
from app.services.pdf_generator import PDFGenerator
from app.services.fipe_client import FipeClient, FipeSearchResult
from app.services.spec_extractor import SpecExtractor
from app.services.spec_validator import SpecValidator
from app.services.linear_meter import LinearMeterCalculator
from app.models.product_specs import ProductSpecs, LinearMeterResult
from app.services.integration_logger import log_anthropic_call, log_serpapi_call
from app.core.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from decimal import Decimal
import os
import hashlib
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def _get_blocked_domains(db: Session) -> set:
    """Carrega os domínios bloqueados do banco de dados"""
    blocked = db.query(BlockedDomain.domain).all()
    return {d.domain for d in blocked}


def _update_progress(db: Session, quote_request: QuoteRequest, step: str, percentage: int, details: str = None):
    """Atualiza o progresso da cotação"""
    quote_request.current_step = step
    quote_request.progress_percentage = percentage
    if details:
        quote_request.step_details = details
    db.commit()
    db.refresh(quote_request)
    logger.info(f"Progress updated: {step} ({percentage}%) - {details}")


class QuoteTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        quote_request_id = args[0] if args else None
        if quote_request_id:
            db = SessionLocal()
            try:
                quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
                if quote_request:
                    # Não sobrescrever status se já foi cancelado pelo usuário
                    if quote_request.status != QuoteStatus.CANCELLED:
                        quote_request.status = QuoteStatus.ERROR
                        quote_request.error_message = str(exc)
                        db.commit()
                    else:
                        logger.info(f"Quote {quote_request_id} was cancelled by user, not marking as error")
            finally:
                db.close()


@celery_app.task(base=QuoteTask, bind=True)
def process_quote_request(self, quote_request_id: int):
    db = SessionLocal()

    try:
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if not quote_request:
            raise ValueError(f"QuoteRequest {quote_request_id} not found")

        logger.info(f"Processing quote request {quote_request_id}")

        # ========================================
        # CHECKPOINT: Inicializar gerenciador
        # ========================================
        checkpoint_mgr = CheckpointManager(db)

        # Tentar claim da cotação (evita processamento duplicado)
        if not checkpoint_mgr.claim_for_processing(quote_request):
            logger.warning(f"Quote {quote_request_id} já está sendo processada por outro worker")
            return

        # Verificar se pode retomar de checkpoint anterior
        can_resume = checkpoint_mgr.can_resume(quote_request)
        resume_checkpoint = checkpoint_mgr.get_resume_checkpoint(quote_request) if can_resume else None

        if resume_checkpoint:
            logger.info(f"Retomando cotação {quote_request_id} do checkpoint: {resume_checkpoint}")
        else:
            checkpoint_mgr.start_processing(quote_request)
            logger.info(f"Iniciando processamento da cotação {quote_request_id}")

        # Iniciando processamento
        _update_progress(db, quote_request, "initializing", 5, "Carregando configurações e integrações...")

        # ========================================
        # CHECKPOINT: Verificar se pode pular análise IA
        # ========================================
        skip_ai_analysis = False
        if resume_checkpoint and quote_request.claude_payload_json:
            # Já tem resultado da IA, pode pular
            skip_ai_analysis = True
            logger.info(f"Pulando análise IA - já existe resultado salvo")

        # Determinar qual provedor de IA usar
        ai_provider = _get_integration_other_setting(db, "ANTHROPIC", "ai_provider")
        if not ai_provider:
            ai_provider = _get_integration_other_setting(db, "OPENAI", "ai_provider")
        if not ai_provider:
            ai_provider = settings.AI_PROVIDER  # default: "anthropic"

        logger.info(f"Using AI provider: {ai_provider}")

        # Inicializar variáveis para model
        model = None
        ai_provider_name = ai_provider.capitalize() if ai_provider else "Anthropic"

        if not skip_ai_analysis:
            # CHECKPOINT: Marcar início da análise IA
            checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.AI_ANALYSIS_START, progress_percentage=10)

            if ai_provider == "openai":
                # Usar OpenAI
                api_key = _get_integration_setting(db, "OPENAI", "api_key")
                if not api_key:
                    api_key = settings.OPENAI_API_KEY

                model = _get_integration_other_setting(db, "OPENAI", "model")
                if not model:
                    model = settings.OPENAI_MODEL

                ai_client = OpenAIClient(api_key=api_key, model=model)
                ai_provider_name = "OpenAI"
            else:
                # Usar Anthropic (padrão)
                api_key = _get_integration_setting(db, "ANTHROPIC", "api_key")
                if not api_key:
                    api_key = settings.ANTHROPIC_API_KEY

                model = _get_integration_other_setting(db, "ANTHROPIC", "model")
                if not model:
                    model = settings.ANTHROPIC_MODEL

                ai_client = ClaudeClient(api_key=api_key, model=model)
                ai_provider_name = "Anthropic"

            logger.info(f"AI Client initialized: {ai_provider_name} with model {model}")

            input_images = db.query(File).filter(
                File.quote_request_id == quote_request_id,
                File.type == FileType.INPUT_IMAGE
            ).all()

            image_data_list = []
            for img_file in input_images:
                with open(img_file.storage_path, 'rb') as f:
                    image_data_list.append(f.read())

            # Analisando entrada (imagem ou texto)
            if image_data_list:
                _update_progress(db, quote_request, "analyzing_image", 10, "Processando imagens e extraindo especificações técnicas...")
            else:
                _update_progress(db, quote_request, "analyzing_text", 10, "Analisando descrição e identificando produto...")

            import asyncio
            analysis_result = asyncio.run(
                ai_client.analyze_item(
                    input_text=quote_request.input_text,
                    image_files=image_data_list if image_data_list else None
                )
            )

            quote_request.claude_payload_json = analysis_result.dict()
            quote_request.search_query_final = analysis_result.query_principal
            db.commit()

            logger.info(f"{ai_provider_name} analysis complete. Query: {analysis_result.query_principal}")

            # Registrar logs de chamadas individuais do AI
            # Determinar o integration_type baseado no ai_provider
            integration_type = "openai" if ai_provider == "openai" else "anthropic"

            for call_log in analysis_result.call_logs:
                # Extrair prompt do call_log (pode ser dict ou objeto)
                prompt_text = None
                if hasattr(call_log, 'prompt'):
                    prompt_text = call_log.prompt
                elif isinstance(call_log, dict):
                    prompt_text = call_log.get('prompt')

                log_anthropic_call(
                    db=db,
                    quote_request_id=quote_request.id,
                    model=model,
                    input_tokens=call_log.input_tokens if hasattr(call_log, 'input_tokens') else call_log.get('input_tokens', 0),
                    output_tokens=call_log.output_tokens if hasattr(call_log, 'output_tokens') else call_log.get('output_tokens', 0),
                    activity=f"[{ai_provider_name}] {call_log.activity if hasattr(call_log, 'activity') else call_log.get('activity', '')}",
                    integration_type=integration_type,
                    request_data={"prompt": prompt_text} if prompt_text else None
                )

            # Mostrar tokens usados
            if analysis_result.total_tokens_used > 0:
                _update_progress(db, quote_request, "analysis_complete", 30, f"Análise completa - {analysis_result.total_tokens_used} tokens processados pela IA")

            # Registrar custo da análise de IA (Anthropic ou OpenAI)
            if analysis_result.total_tokens_used > 0:
                _register_ai_cost(db, quote_request, model, analysis_result.total_tokens_used, ai_provider)

            # ========================================
            # CHECKPOINT: Salvar após análise IA concluída
            # ========================================
            checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.AI_ANALYSIS_DONE, progress_percentage=30)

        else:
            # Recuperar analysis_result do JSON salvo
            from app.services.claude_client import ClaudeAnalysisResult
            analysis_result = ClaudeAnalysisResult(**quote_request.claude_payload_json)
            logger.info(f"Análise IA recuperada do checkpoint. Query: {analysis_result.query_principal}")

        # Preparando busca
        _update_progress(db, quote_request, "preparing_search", 40, "Preparando busca de preços em lojas online...")

        # Verificar se é veículo (processamento via FIPE)
        if analysis_result.tipo_processamento == "FIPE" and analysis_result.fipe_api:
            logger.info(f"Detected vehicle - using FIPE API flow")
            use_fallback = _process_fipe_quote(db, quote_request, analysis_result)
            if not use_fallback:
                return
            # FIPE falhou, continuar com Google Shopping usando query de fallback
            logger.info(f"FIPE failed, falling back to Google Shopping with query: {analysis_result.query_principal}")

        # Fluxo padrão: Google Shopping via SerpAPI
        serpapi_key = _get_integration_setting(db, "SERPAPI", "api_key")
        if not serpapi_key:
            serpapi_key = settings.SERPAPI_API_KEY

        # Usar config_version_id do projeto (se houver) para buscar parâmetros
        config_version_id = quote_request.config_version_id

        serpapi_location = _get_parameter(db, "serpapi_location", "Brazil", config_version_id)
        blocked_domains = _get_blocked_domains(db)
        search_provider = SerpApiProvider(
            api_key=serpapi_key,
            engine=settings.SERPAPI_ENGINE,
            location=serpapi_location,
            blocked_domains=blocked_domains
        )

        # Get parameters for search (prioridade: projeto > global > default)
        num_quotes = int(_get_parameter(db, "numero_cotacoes_por_pesquisa", 3, config_version_id))
        variacao_maxima = float(_get_parameter(db, "variacao_maxima_percent", 25, config_version_id)) / 100
        enable_price_mismatch = _get_parameter(db, "enable_price_mismatch_validation", True, config_version_id)

        # Novos parâmetros v2.0: validação de specs e metro linear
        enable_spec_extraction = _get_parameter(db, "enable_spec_extraction", False, config_version_id)
        enable_spec_validation = _get_parameter(db, "enable_spec_validation", False, config_version_id)
        spec_dimension_tolerance = float(_get_parameter(db, "spec_dimension_tolerance", 0.20, config_version_id))
        enable_linear_meter = _get_parameter(db, "enable_linear_meter", False, config_version_id)
        linear_meter_min_products = int(_get_parameter(db, "linear_meter_min_products", 2, config_version_id))

        logger.info(f"Quote {quote_request_id} using parameters: num_quotes={num_quotes}, variacao_maxima={variacao_maxima*100}%, enable_price_mismatch={enable_price_mismatch}, config_version_id={config_version_id}")
        if enable_spec_extraction or enable_spec_validation or enable_linear_meter:
            logger.info(f"  v2.0 features: spec_extraction={enable_spec_extraction}, spec_validation={enable_spec_validation}, linear_meter={enable_linear_meter}")

        # Validar se a query foi gerada
        if not analysis_result.query_principal or not analysis_result.query_principal.strip():
            raise ValueError("Claude não conseguiu gerar uma query de busca válida. Verifique a descrição do item e tente novamente.")

        # ========================================
        # CHECKPOINT: Verificar se pode pular busca Google Shopping
        # ========================================
        skip_shopping_search = False
        if resume_checkpoint and quote_request.google_shopping_response_json:
            # Já tem resultados do Google Shopping, pode pular
            skip_shopping_search = True
            logger.info(f"Pulando busca Google Shopping - já existe resultado salvo")

        if not skip_shopping_search:
            # CHECKPOINT: Marcar início da busca Google Shopping
            checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.SHOPPING_SEARCH_START, progress_percentage=40)

            # Buscando produtos no Google Shopping (sem chamar Immersive API ainda)
            _update_progress(db, quote_request, "searching_products", 50, f"Buscando '{analysis_result.query_principal}' no Google Shopping...")

            # NOVO FLUXO: Buscar produtos do Google Shopping SEM chamar Immersive API
            # A Immersive API será chamada durante o loop de extração, produto por produto
            shopping_products, shopping_log = asyncio.run(
                search_provider.get_shopping_products(
                    query=analysis_result.query_principal
                )
            )

            logger.info(f"Found {len(shopping_products)} shopping products (filtered)")
            logger.info(f"Shopping log: {shopping_log.model_dump_json()}")

            # Registrar chamada inicial do Google Shopping
            log_serpapi_call(
                db=db,
                quote_request_id=quote_request.id,
                api_used="google_shopping",
                search_url=f"https://serpapi.com/search?engine=google_shopping&q={analysis_result.query_principal}",
                activity=f"Busca inicial no Google Shopping: {analysis_result.query_principal}",
                request_data={"query": analysis_result.query_principal},
                response_summary={
                    "total_raw_products": shopping_log.total_raw_products,
                    "after_source_filter": shopping_log.after_source_filter,
                    "after_price_filter": shopping_log.after_price_filter
                },
                product_link=None
            )

            # Salvar resposta bruta do Google Shopping para consulta
            quote_request.google_shopping_response_json = {
                "raw_api_response": shopping_log.raw_shopping_response,
                "processed_results": {
                    "results_count": len(shopping_products),
                    "products": [
                        {
                            "title": p.title,
                            "price": p.price,
                            "extracted_price": float(p.extracted_price) if p.extracted_price else None,
                            "source": p.source,
                            "has_immersive_api": bool(p.serpapi_immersive_product_api)
                        } for p in shopping_products
                    ]
                },
                "shopping_log": shopping_log.model_dump(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            db.commit()

            # ========================================
            # CHECKPOINT: Salvar após busca Google Shopping
            # ========================================
            checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.SHOPPING_SEARCH_DONE, progress_percentage=50)
        else:
            # Recuperar shopping_products do JSON salvo
            saved_data = quote_request.google_shopping_response_json
            if saved_data and "processed_results" in saved_data:
                # Reconstruir lista de ShoppingProduct
                shopping_products = []
                for p_data in saved_data["processed_results"].get("products", []):
                    product = ShoppingProduct(
                        title=p_data.get("title", ""),
                        price=p_data.get("price", ""),
                        extracted_price=Decimal(str(p_data.get("extracted_price", 0))) if p_data.get("extracted_price") else None,
                        source=p_data.get("source", ""),
                        serpapi_immersive_product_api=p_data.get("serpapi_immersive_product_api")
                    )
                    shopping_products.append(product)
                logger.info(f"Busca Google Shopping recuperada do checkpoint. {len(shopping_products)} produtos")
            else:
                shopping_products = []
                logger.warning(f"Não foi possível recuperar produtos do checkpoint")

        # ============================================================================
        # SISTEMA DE COTAÇÃO DE PREÇOS - LÓGICA DE BLOCOS
        # ============================================================================
        # Objetivo: Obter NUM_COTACOES válidas de um ÚNICO BLOCO garantindo
        # variação máxima de VAR_MAX_PERCENT entre menor e maior preço.
        # ============================================================================

        # ========================================
        # CHECKPOINT: Marcar início da extração de preços
        # ========================================
        checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.PRICE_EXTRACTION_START, progress_percentage=55)

        _update_progress(db, quote_request, "extracting_prices", 60, f"Processando {len(shopping_products)} produtos...")

        # Estado global da cotação
        valid_sources = []                    # Fontes validadas
        valid_sources_by_product_key = {}     # {product_key: source}
        validated_product_keys = set()        # Produtos já validados com sucesso
        failed_product_keys = set()           # Produtos que falharam (descartados)
        domains_in_block = set()              # Domínios já usados no bloco atual
        urls_seen = set()                     # URLs já usadas

        # Estatísticas para log detalhado
        search_stats = {
            "products_tested": 0,
            "blocks_recalculated": 0,
            "immersive_api_calls": 0,
            "tolerance_increases": 0,
            "validation_failures": [],
            "successful_products": [],
            # Novos campos para histórico de blocos
            "initial_products_sorted": [],  # Lista inicial ordenada por preço
            "block_history": [],  # Histórico de cada iteração de bloco
            # Configuração de validação de preços
            "enable_price_mismatch": enable_price_mismatch,
            "price_source": "site" if enable_price_mismatch else "google",
            "price_mismatch_note": "Validação de preço HABILITADA: rejeita produtos com diferença > 5% entre Google e Site" if enable_price_mismatch else "Validação de preço DESABILITADA: usa preço do Google Shopping (consistente com seleção de bloco)",
        }

        # Parâmetros
        INCREMENTO_VAR = 0.05  # 5% de aumento na tolerância quando fallback
        current_var_max = variacao_maxima  # Variação máxima atual

        # ============================================================================
        # FUNÇÕES HELPER
        # ============================================================================
        def _normalize_price(price) -> str:
            """Normaliza preço para string com 2 casas decimais."""
            try:
                return f"{float(price):.2f}"
            except (ValueError, TypeError):
                return str(price)

        def _make_product_key(title: str, price) -> str:
            """Cria chave normalizada para produto."""
            return f"{title}_{_normalize_price(price)}"

        def _form_blocks(products, max_variation, min_size):
            """
            ETAPA 1.4: Forma blocos consecutivos de produtos onde:
            - Mínimo de min_size produtos
            - Variação: (preço_max - preço_min) / preço_min × 100 ≤ max_variation
            Retorna lista de blocos ordenada por: maior tamanho, depois menor preço inicial.
            """
            if not products:
                return []

            blocks = []
            for start_idx in range(len(products)):
                start_product = products[start_idx]
                if not start_product.extracted_price:
                    continue

                min_price = float(start_product.extracted_price)
                max_allowed = min_price * (1 + max_variation)

                block = []
                for product in products[start_idx:]:
                    if product.extracted_price and float(product.extracted_price) <= max_allowed:
                        block.append(product)
                    else:
                        break  # Produtos estão ordenados, então podemos parar

                if len(block) >= min_size:
                    blocks.append({
                        "products": block,
                        "min_price": min_price,
                        "max_price": float(block[-1].extracted_price),
                        "size": len(block)
                    })

            # Ordenar: maior tamanho primeiro, depois menor preço inicial
            blocks.sort(key=lambda b: (-b["size"], b["min_price"]))
            return blocks

        def _get_block_id(block):
            """Gera um ID único para o bloco baseado nos produtos."""
            keys = sorted([_make_product_key(p.title, p.extracted_price) for p in block])
            return hash(tuple(keys))

        def _rank_blocks(blocks, validated_keys, failed_keys):
            """
            Retorna lista de blocos ordenados por prioridade, com métricas.
            Blocos sem potencial suficiente são excluídos.
            """
            ranked = []

            for block_info in blocks:
                block = block_info["products"]
                block_keys = {_make_product_key(p.title, p.extracted_price) for p in block}

                valid_in_block = len(validated_keys & block_keys)
                failed_in_block = len(failed_keys & block_keys)
                untried_in_block = len(block_keys - validated_keys - failed_keys)

                # Potencial = validados + não testados
                potential = valid_in_block + untried_in_block

                # Se não pode atingir NUM_COTACOES, pular este bloco
                if potential < num_quotes:
                    continue

                # Score: prioriza blocos com mais validados, mais não testados, menor preço
                score = (valid_in_block, untried_in_block, -block_info["min_price"])

                ranked.append({
                    "block": block,
                    "block_info": block_info,
                    "score": score,
                    "valid_in_block": valid_in_block,
                    "untried_count": untried_in_block,
                    "potential": potential,
                    "block_id": _get_block_id(block)
                })

            # Ordenar por score decrescente
            ranked.sort(key=lambda x: x["score"], reverse=True)
            return ranked

        # ============================================================================
        # FUNÇÃO ALTERNATIVA: EXTRAÇÃO SEM VALIDAÇÃO DE PREÇO (enable_price_mismatch=False)
        # ============================================================================
        # Este fluxo é usado quando a validação de preço está DESABILITADA.
        # Diferenças em relação ao fluxo principal (extract_prices_with_blocks):
        # - NÃO extrai preço do site
        # - NÃO compara preço site vs Google
        # - Usa preço do Google Shopping diretamente
        # - Critério de sucesso: URL válida + domínio único (screenshot opcional)
        # ============================================================================
        async def extract_prices_google_only():
            """
            Fluxo simplificado para quando enable_price_mismatch=False.
            Usa apenas o preço do Google Shopping, sem extrair/validar preço do site.

            Etapas:
            1. Formar blocos com produtos disponíveis (preço Google)
            2. Escolher o melhor bloco
            3. Para cada produto do bloco:
               - Obter URL via Immersive API
               - Verificar URL única e domínio não repetido
               - Capturar screenshot (opcional - se falhar, aceita sem)
               - Salvar QuoteSource com preço do Google
            4. Se falhar → Recalcular blocos → voltar ao passo 2
            5. Aumentar tolerância se não conseguir formar blocos válidos
            """
            from app.models.quote_source import ExtractionMethod
            nonlocal valid_sources, valid_sources_by_product_key, validated_product_keys
            nonlocal failed_product_keys, domains_in_block, urls_seen, current_var_max

            all_products = list(shopping_products)
            max_tolerance_increases = 5
            max_iterations = 100
            global_iteration = 0
            tolerance_round = 0

            logger.info(f"=== INICIANDO FLUXO GOOGLE_ONLY (sem validação de preço) ===")
            logger.info(f"Parâmetros: num_quotes={num_quotes}, variacao_maxima={variacao_maxima*100:.0f}%")

            # Registrar lista inicial de produtos ordenados
            sorted_products = sorted(
                [p for p in all_products if p.extracted_price],
                key=lambda p: float(p.extracted_price)
            )
            search_stats["initial_products_sorted"] = [
                {
                    "index": idx,
                    "title": p.title,
                    "price": float(p.extracted_price),
                    "source": p.source
                }
                for idx, p in enumerate(sorted_products)
            ]

            try:
                while tolerance_round <= max_tolerance_increases:
                    if tolerance_round > 0:
                        current_var_max += INCREMENTO_VAR
                        search_stats["tolerance_increases"] += 1
                        logger.info(f"=== FALLBACK #{tolerance_round}: Aumentando tolerância para {current_var_max*100:.0f}% ===")
                        domains_in_block.clear()

                    while global_iteration < max_iterations:
                        global_iteration += 1

                        # Produtos disponíveis = todos menos os que falharam
                        available_products = [
                            p for p in all_products
                            if _make_product_key(p.title, p.extracted_price) not in failed_product_keys
                        ]

                        if not available_products:
                            logger.info(f"Iteração {global_iteration}: Sem produtos disponíveis")
                            break

                        # Registrar produtos disponíveis para esta iteração
                        available_for_calc = {
                            "count": len(available_products),
                            "indices": [
                                next((i for i, sp in enumerate(sorted_products)
                                      if _make_product_key(sp.title, sp.extracted_price) == _make_product_key(p.title, p.extracted_price)), -1)
                                for p in available_products
                            ],
                            "discarded_failures": len(failed_product_keys),
                            "products": [
                                {
                                    "index": next((i for i, sp in enumerate(sorted_products)
                                                   if _make_product_key(sp.title, sp.extracted_price) == _make_product_key(p.title, p.extracted_price)), -1),
                                    "title": p.title,
                                    "price": float(p.extracted_price),
                                    "source": p.source,
                                    "status": "validated" if _make_product_key(p.title, p.extracted_price) in validated_product_keys else "untried"
                                }
                                for p in sorted(available_products, key=lambda x: float(x.extracted_price))
                            ]
                        }

                        # ETAPA 1: Formar blocos
                        blocks = _form_blocks(available_products, current_var_max, num_quotes)

                        if not blocks:
                            logger.info(f"Iteração {global_iteration}: Nenhum bloco formado com var_max={current_var_max*100:.0f}%")
                            break

                        # ETAPA 2: Rankear e selecionar melhor bloco
                        ranked_blocks = _rank_blocks(blocks, validated_product_keys, failed_product_keys)

                        if not ranked_blocks:
                            logger.info(f"Iteração {global_iteration}: Nenhum bloco elegível")
                            break

                        best = ranked_blocks[0]
                        block = best["block"]
                        block_info = best["block_info"]

                        search_stats["blocks_recalculated"] += 1

                        block_keys = {_make_product_key(p.title, p.extracted_price) for p in block}
                        valid_in_block = len(validated_product_keys & block_keys)
                        untried_in_block = [p for p in block
                            if _make_product_key(p.title, p.extracted_price) not in validated_product_keys
                            and _make_product_key(p.title, p.extracted_price) not in failed_product_keys]

                        # Registro do histórico
                        block_record = {
                            "iteration": global_iteration,
                            "tolerance_round": tolerance_round,
                            "var_max_percent": current_var_max * 100,
                            "total_blocks_formed": len(blocks),
                            "blocks_eligible": len(ranked_blocks),
                            "block_size": len(block),
                            "price_range": {
                                "min": float(block[0].extracted_price),
                                "max": float(block[-1].extracted_price)
                            },
                            "validated_in_block": valid_in_block,
                            "untried_count": len(untried_in_block),
                            "products_in_block": [
                                {
                                    "index": next((i for i, sp in enumerate(sorted_products)
                                                   if _make_product_key(sp.title, sp.extracted_price) == _make_product_key(p.title, p.extracted_price)), -1),
                                    "title": p.title,
                                    "price": float(p.extracted_price),
                                    "source": p.source,
                                    "status": "validated" if _make_product_key(p.title, p.extracted_price) in validated_product_keys else "untried"
                                }
                                for p in block
                            ],
                            "products_indices": [
                                next((i for i, sp in enumerate(sorted_products)
                                      if _make_product_key(sp.title, sp.extracted_price) == _make_product_key(p.title, p.extracted_price)), -1)
                                for p in block
                            ],
                            "available_for_calculation": available_for_calc,
                            "status_before": {
                                "valid_count": valid_in_block,
                                "needed": num_quotes - valid_in_block
                            },
                            "tests": [],
                            "flow_type": "google_only"
                        }

                        logger.info(
                            f"Iteração {global_iteration} (tol {tolerance_round}): "
                            f"{len(blocks)} blocos, {len(ranked_blocks)} elegíveis. "
                            f"Melhor: {len(block)} produtos (R$ {block[0].extracted_price:.2f} - R$ {block[-1].extracted_price:.2f}), "
                            f"{valid_in_block} validados, {len(untried_in_block)} a testar"
                        )

                        # VERIFICAÇÃO DE SUCESSO ANTECIPADO
                        if valid_in_block >= num_quotes:
                            logger.info(f"✅ SUCESSO! Bloco já tem {valid_in_block} cotações válidas")
                            block_record["result"] = "success_early"
                            search_stats["block_history"].append(block_record)

                            valid_sources = [
                                s for pk, s in valid_sources_by_product_key.items()
                                if pk in block_keys
                            ]
                            for pk, source in valid_sources_by_product_key.items():
                                if pk not in block_keys:
                                    source.is_accepted = False
                            return

                        # ETAPA 3: Testar produtos do bloco
                        for product in untried_in_block:
                            product_key = _make_product_key(product.title, product.extracted_price)
                            google_price = product.extracted_price

                            # Verificar se já atingimos a meta
                            valid_in_block_now = len(validated_product_keys & block_keys)
                            if valid_in_block_now >= num_quotes:
                                logger.info(f"✅ SUCESSO! Atingido {valid_in_block_now} cotações no bloco")
                                block_record["result"] = "success"
                                search_stats["block_history"].append(block_record)

                                valid_sources = [
                                    s for pk, s in valid_sources_by_product_key.items()
                                    if pk in block_keys
                                ]
                                for pk, source in valid_sources_by_product_key.items():
                                    if pk not in block_keys:
                                        source.is_accepted = False
                                return

                            logger.info(f"  → Validando (Google Only): {product.source} - R$ {google_price}")
                            search_stats["products_tested"] += 1

                            # ========================================
                            # CHECKPOINT: Atualizar heartbeat a cada produto
                            # ========================================
                            checkpoint_mgr.update_heartbeat(quote_request)

                            test_record = {
                                "product_index": next((i for i, sp in enumerate(sorted_products)
                                                       if _make_product_key(sp.title, sp.extracted_price) == product_key), -1),
                                "title": product.title,
                                "source": product.source,
                                "google_price": float(google_price),
                                "result": None,
                                "flow_type": "google_only"
                            }

                            try:
                                # PASSO 1: Obter URL via Immersive API
                                if not product.serpapi_immersive_product_api:
                                    raise ValueError("NO_STORE_LINK: Produto sem link Immersive API")

                                search_stats["immersive_api_calls"] += 1
                                store_result = await search_provider.get_store_link_for_product(product)

                                if not store_result or not store_result.url:
                                    raise ValueError("NO_STORE_LINK: Não foi possível obter URL do site")

                                # Registrar chamada Immersive
                                log_serpapi_call(
                                    db=db,
                                    quote_request_id=quote_request.id,
                                    api_used="google_shopping_immersive",
                                    search_url=product.serpapi_immersive_product_api,
                                    activity=f"Obtendo link da loja para: {product.title[:50]}",
                                    request_data={"product_title": product.title},
                                    response_summary={"store_url": store_result.url, "domain": store_result.domain},
                                    product_link=store_result.url
                                )

                                # PASSO 2: Validações de domínio/URL
                                if search_provider._is_blocked_domain(store_result.domain):
                                    raise ValueError(f"BLOCKED_DOMAIN: {store_result.domain}")

                                if search_provider._is_foreign_domain(store_result.domain):
                                    raise ValueError(f"FOREIGN_DOMAIN: {store_result.domain}")

                                if search_provider._is_listing_url(store_result.url):
                                    raise ValueError(f"LISTING_URL: {store_result.url[:50]}")

                                # PASSO 3: Verificar URL duplicada
                                if store_result.url in urls_seen:
                                    raise ValueError(f"URL_DUPLICADA: {store_result.url}")
                                urls_seen.add(store_result.url)

                                # PASSO 4: Capturar screenshot (OBRIGATÓRIO)
                                from app.services.price_extractor import PriceExtractor
                                extractor = PriceExtractor()
                                screenshot_bytes = await extractor.capture_screenshot_only(store_result.url)

                                if not screenshot_bytes:
                                    raise ValueError(f"SCREENSHOT_ERROR: Falha ao capturar screenshot de {store_result.url[:50]}")

                                file_hash = hashlib.sha256(screenshot_bytes).hexdigest()
                                screenshot_path = f"storage/screenshots/{file_hash}_screenshot.png"

                                # Salvar arquivo no disco
                                os.makedirs("storage/screenshots", exist_ok=True)
                                with open(screenshot_path, "wb") as f:
                                    f.write(screenshot_bytes)

                                # Criar registro no banco
                                screenshot_file = File(
                                    type=FileType.SCREENSHOT,
                                    mime_type="image/png",
                                    storage_path=screenshot_path,
                                    sha256=file_hash,
                                    quote_request_id=quote_request_id
                                )
                                db.add(screenshot_file)
                                db.flush()

                                logger.info(f"    Screenshot capturado: {screenshot_path}")

                                # ✅ SUCESSO - Criar QuoteSource com preço do Google
                                source = QuoteSource(
                                    quote_request_id=quote_request_id,
                                    url=store_result.url,
                                    domain=store_result.domain,
                                    page_title=product.title,
                                    price_value=Decimal(str(google_price)),
                                    currency="BRL",
                                    extraction_method=ExtractionMethod.GOOGLE_SHOPPING,
                                    screenshot_file_id=screenshot_file.id if screenshot_file else None,
                                    is_accepted=True
                                )
                                db.add(source)
                                db.flush()

                                valid_sources.append(source)
                                valid_sources_by_product_key[product_key] = source
                                validated_product_keys.add(product_key)

                                logger.info(f"  ✓ Validado [{len(validated_product_keys & block_keys)}/{num_quotes}]: {store_result.domain} - R$ {google_price} (preço Google)")

                                test_record["result"] = "success"
                                test_record["extracted_price"] = float(google_price)
                                test_record["final_price"] = float(google_price)
                                test_record["price_source"] = "google"
                                test_record["url"] = store_result.url
                                test_record["domain"] = store_result.domain
                                test_record["has_screenshot"] = screenshot_file is not None
                                block_record["tests"].append(test_record)

                                search_stats["successful_products"].append({
                                    "title": product.title,
                                    "google_price": float(google_price),
                                    "extracted_price": float(google_price),
                                    "final_price": float(google_price),
                                    "price_source": "google",
                                    "url": store_result.url,
                                    "domain": store_result.domain,
                                    "has_screenshot": screenshot_file is not None
                                })

                            except Exception as e:
                                error_msg = str(e)
                                logger.error(f"  ✗ Falha: {error_msg[:100]}")
                                failed_product_keys.add(product_key)

                                # Determinar tipo de falha
                                failure_step = "UNKNOWN"
                                failure_reason = CaptureFailureReason.OTHER
                                if "NO_STORE_LINK" in error_msg:
                                    failure_step = "IMMERSIVE_API"
                                    failure_reason = CaptureFailureReason.NO_STORE_LINK
                                elif "BLOCKED_DOMAIN" in error_msg:
                                    failure_step = "DOMAIN_VALIDATION"
                                    failure_reason = CaptureFailureReason.BLOCKED_DOMAIN
                                elif "FOREIGN_DOMAIN" in error_msg:
                                    failure_step = "DOMAIN_VALIDATION"
                                    failure_reason = CaptureFailureReason.FOREIGN_DOMAIN
                                elif "LISTING_URL" in error_msg:
                                    failure_step = "URL_VALIDATION"
                                    failure_reason = CaptureFailureReason.LISTING_URL
                                elif "URL_DUPLICADA" in error_msg:
                                    failure_step = "URL_VALIDATION"
                                    failure_reason = CaptureFailureReason.DUPLICATE_URL
                                elif "SCREENSHOT_ERROR" in error_msg:
                                    failure_step = "SCREENSHOT"
                                    failure_reason = CaptureFailureReason.SCREENSHOT_ERROR

                                test_record["result"] = "failed"
                                test_record["failure_step"] = failure_step
                                test_record["error_message"] = error_msg[:200]
                                block_record["tests"].append(test_record)

                                search_stats["validation_failures"].append({
                                    "title": product.title,
                                    "source": product.source,
                                    "google_price": float(google_price) if google_price else None,
                                    "failure_step": failure_step,
                                    "error_message": error_msg[:200],
                                    "url": store_result.url if 'store_result' in dir() and store_result else None,
                                    "domain": store_result.domain if 'store_result' in dir() and store_result else None
                                })

                                # Salvar falha no banco
                                try:
                                    # URL é obrigatório - usar URL da loja se disponível, senão usar API URL
                                    failure_url = (store_result.url if store_result else None) or product.serpapi_immersive_product_api or f"google_shopping://{product.title[:100]}"
                                    failure_domain = (store_result.domain if store_result else None)

                                    failure_record = QuoteSourceFailure(
                                        quote_request_id=quote_request_id,
                                        product_title=f"{product.title} ({product.source})",  # Incluir fonte no título
                                        google_price=Decimal(str(google_price)) if google_price else None,
                                        url=failure_url,
                                        domain=failure_domain,
                                        failure_reason=failure_reason,
                                        error_message=f"[{failure_step}] {error_msg[:450]}"  # Incluir step no error_message
                                    )
                                    db.add(failure_record)
                                    db.flush()
                                except Exception as save_error:
                                    logger.warning(f"Erro ao salvar falha: {save_error}")
                                    db.rollback()

                        # Fim do for - verificar resultado do bloco
                        valid_in_block_final = len(validated_product_keys & block_keys)

                        block_record["status_after"] = {
                            "valid_count": valid_in_block_final,
                            "successes_this_block": valid_in_block_final - valid_in_block,
                            "failures_this_block": len([t for t in block_record["tests"] if t["result"] == "failed"])
                        }

                        if valid_in_block_final >= num_quotes:
                            logger.info(f"✅ SUCESSO! {valid_in_block_final} cotações válidas no bloco")
                            block_record["result"] = "success"
                            search_stats["block_history"].append(block_record)

                            valid_sources = [
                                s for pk, s in valid_sources_by_product_key.items()
                                if pk in block_keys
                            ]
                            for pk, source in valid_sources_by_product_key.items():
                                if pk not in block_keys:
                                    source.is_accepted = False
                            return

                        # Bloco falhou - recalcular
                        block_record["result"] = "failed"
                        block_record["final_valid_count"] = valid_in_block_final
                        search_stats["block_history"].append(block_record)
                        logger.info(
                            f"  ❌ BLOCO FALHOU: {valid_in_block_final}/{num_quotes} válidos. Recalculando..."
                        )

                    # Fim do while interno
                    tolerance_round += 1
                    logger.info(f"Tolerância {current_var_max*100:.0f}% esgotada após {global_iteration} iterações")

                # Fallback: usar melhor bloco encontrado
                total_validated = len(validated_product_keys)
                logger.warning(
                    f"Não foi possível obter {num_quotes} cotações em um único bloco. "
                    f"Total validado: {total_validated}. Tolerância final: {current_var_max*100:.0f}%"
                )

                best_block_keys = set()
                best_valid_count = 0

                for block_record in search_stats["block_history"]:
                    products = block_record.get("products_in_block", [])
                    block_product_keys = set()
                    for p in products:
                        pk = _make_product_key(p.get("title", ""), p.get("price", 0))
                        block_product_keys.add(pk)
                    valid_count = len(validated_product_keys & block_product_keys)
                    if valid_count > best_valid_count:
                        best_valid_count = valid_count
                        best_block_keys = block_product_keys

                if best_block_keys and best_valid_count > 0:
                    logger.info(f"Selecionando melhor bloco com {best_valid_count} validados como fallback")
                    valid_sources = [
                        s for pk, s in valid_sources_by_product_key.items()
                        if pk in best_block_keys
                    ]
                    for pk, source in valid_sources_by_product_key.items():
                        if pk not in best_block_keys:
                            source.is_accepted = False

            except Exception as e:
                logger.error(f"Erro em extract_prices_google_only: {str(e)}")
                raise

        # ============================================================================
        # FUNÇÃO PRINCIPAL DE EXTRAÇÃO (COM VALIDAÇÃO DE PREÇO)
        # ============================================================================
        async def extract_prices_with_blocks():
            """
            Implementação corrigida - RECALCULA blocos após cada falha:
            1. Formar blocos com produtos disponíveis
            2. Escolher o melhor bloco
            3. Testar produtos do bloco
            4. Se falhar → RECALCULAR blocos (produtos falhos removidos) → voltar ao passo 2
            5. Só aumentar tolerância quando não consegue formar blocos válidos
            """
            from app.models.quote_source import ExtractionMethod
            nonlocal valid_sources, valid_sources_by_product_key, validated_product_keys
            nonlocal failed_product_keys, domains_in_block, urls_seen, current_var_max

            all_products = list(shopping_products)
            max_tolerance_increases = 5  # Máximo de aumentos de tolerância
            max_iterations = 100  # Limite de segurança

            async with PriceExtractor() as extractor:
                first_run = True
                global_iteration = 0

                # LOOP EXTERNO: Tolerância de variação
                for tolerance_round in range(max_tolerance_increases + 1):
                    if tolerance_round > 0:
                        # Aumentar tolerância
                        current_var_max += INCREMENTO_VAR
                        search_stats["tolerance_increases"] += 1
                        logger.info(f"=== FALLBACK #{tolerance_round}: Aumentando tolerância para {current_var_max*100:.0f}% ===")
                        # Resetar domínios do bloco mas manter validados
                        domains_in_block.clear()

                    # LOOP INTERNO: Formar blocos → tentar → recalcular → repetir
                    while global_iteration < max_iterations:
                        global_iteration += 1

                        # Construir lista de produtos disponíveis (excluindo falhos)
                        available_products = [
                            p for p in all_products
                            if _make_product_key(p.title, p.extracted_price) not in failed_product_keys
                        ]

                        if not available_products:
                            logger.info(f"Iteração {global_iteration}: Nenhum produto disponível")
                            break

                        # Ordenar por preço crescente
                        available_products.sort(key=lambda p: float(p.extracted_price) if p.extracted_price else 0)

                        # Registrar lista inicial de produtos (apenas na primeira vez)
                        if first_run:
                            first_run = False
                            search_stats["initial_products_sorted"] = [
                                {
                                    "index": idx,
                                    "title": p.title[:60],
                                    "source": p.source,
                                    "price": float(p.extracted_price) if p.extracted_price else 0
                                }
                                for idx, p in enumerate(available_products)
                            ]

                        # ETAPA 1: Formar blocos com produtos disponíveis
                        blocks = _form_blocks(available_products, current_var_max, num_quotes)

                        if not blocks:
                            logger.info(f"Iteração {global_iteration}: Nenhum bloco pode ser formado com var_max={current_var_max*100:.0f}%")
                            break  # Ir para próxima tolerância

                        # ETAPA 2: Rankear e selecionar melhor bloco
                        ranked_blocks = _rank_blocks(blocks, validated_product_keys, failed_product_keys)

                        if not ranked_blocks:
                            logger.info(f"Iteração {global_iteration}: Nenhum bloco elegível (todos sem potencial suficiente)")
                            break  # Ir para próxima tolerância

                        # Pegar o melhor bloco
                        best = ranked_blocks[0]
                        block = best["block"]
                        block_info = best["block_info"]

                        search_stats["blocks_recalculated"] += 1

                        # Calcular métricas atuais do bloco
                        block_keys = {_make_product_key(p.title, p.extracted_price) for p in block}
                        valid_in_block = len(validated_product_keys & block_keys)
                        untried_in_block = [p for p in block
                            if _make_product_key(p.title, p.extracted_price) not in validated_product_keys
                            and _make_product_key(p.title, p.extracted_price) not in failed_product_keys]

                        # Criar registro do histórico de bloco
                        block_record = {
                            "iteration": global_iteration,
                            "tolerance_round": tolerance_round,
                            "var_max_percent": current_var_max * 100,
                            "total_blocks_formed": len(blocks),
                            "blocks_eligible": len(ranked_blocks),
                            "block_size": len(block),
                            "price_range": {
                                "min": float(block[0].extracted_price),
                                "max": float(block[-1].extracted_price)
                            },
                            "validated_in_block": valid_in_block,
                            "untried_count": len(untried_in_block),
                            "products_in_block": [
                                {
                                    "index": available_products.index(p) if p in available_products else -1,
                                    "title": p.title[:40],
                                    "source": p.source,
                                    "price": float(p.extracted_price) if p.extracted_price else 0,
                                    "status": "validated" if _make_product_key(p.title, p.extracted_price) in validated_product_keys
                                             else "failed" if _make_product_key(p.title, p.extracted_price) in failed_product_keys
                                             else "untried"
                                }
                                for p in block
                            ],
                            "tests": [],
                            "result": None
                        }

                        logger.info(
                            f"Iteração {global_iteration} (tol {tolerance_round}): "
                            f"{len(blocks)} blocos formados, {len(ranked_blocks)} elegíveis. "
                            f"Melhor bloco: {len(block)} produtos (R$ {block[0].extracted_price:.2f} - R$ {block[-1].extracted_price:.2f}), "
                            f"{valid_in_block} validados, {len(untried_in_block)} a testar"
                        )

                        # VERIFICAÇÃO DE SUCESSO ANTECIPADO
                        if valid_in_block >= num_quotes:
                            logger.info(f"✅ SUCESSO! Bloco já tem {valid_in_block} cotações válidas")
                            block_record["result"] = "success_early"
                            search_stats["block_history"].append(block_record)

                            # Filtrar fontes para manter apenas as do bloco vencedor
                            valid_sources = [
                                s for pk, s in valid_sources_by_product_key.items()
                                if pk in block_keys
                            ]

                            # Marcar como não aceitas as fontes fora do bloco vencedor
                            for pk, source in valid_sources_by_product_key.items():
                                if pk not in block_keys:
                                    source.is_accepted = False
                                    logger.info(f"  Fonte {source.domain} marcada como não aceita (fora do bloco vencedor)")

                            return  # Sucesso!

                        # ETAPA 3: Testar TODOS os produtos do bloco
                        # Só recalculamos blocos APÓS testar todos os produtos do bloco atual

                        for product in untried_in_block:
                            product_key = _make_product_key(product.title, product.extracted_price)

                            # Verificar se já atingimos a meta
                            valid_in_block_now = len(validated_product_keys & block_keys)
                            if valid_in_block_now >= num_quotes:
                                logger.info(f"✅ SUCESSO! Atingido {valid_in_block_now} cotações no bloco")
                                block_record["result"] = "success"
                                search_stats["block_history"].append(block_record)

                                # Filtrar fontes para manter apenas as do bloco vencedor
                                valid_sources = [
                                    s for pk, s in valid_sources_by_product_key.items()
                                    if pk in block_keys
                                ]

                                # Marcar como não aceitas as fontes fora do bloco vencedor
                                for pk, source in valid_sources_by_product_key.items():
                                    if pk not in block_keys:
                                        source.is_accepted = False
                                        logger.info(f"  Fonte {source.domain} marcada como não aceita (fora do bloco vencedor)")

                                return  # Sucesso!

                            # Processar produto
                            logger.info(f"  → Validando: {product.source} - R$ {product.extracted_price}")
                            search_stats["products_tested"] += 1

                            # ========================================
                            # CHECKPOINT: Atualizar heartbeat a cada produto
                            # ========================================
                            checkpoint_mgr.update_heartbeat(quote_request)

                            # Preparar registro do teste
                            test_record = {
                                "product_index": available_products.index(product) if product in available_products else -1,
                                "title": product.title[:50],
                                "source": product.source,
                                "google_price": float(product.extracted_price) if product.extracted_price else 0,
                                "result": None,
                                "failure_step": None,
                                "error_message": None,
                                "extracted_price": None,
                                "domain": None
                            }

                            try:
                                # PASSO 1: Chamar Immersive API
                                store_result = await search_provider.get_store_link_for_product(product)
                                search_stats["immersive_api_calls"] += 1

                                if not store_result:
                                    raise ValueError("NO_STORE_LINK: Immersive API não retornou URL")

                                # Registrar chamada
                                log_serpapi_call(
                                    db=db, quote_request_id=quote_request.id,
                                    api_used="google_immersive_product", search_url="",
                                    activity=f"Busca de loja para: {product.title[:50]}...",
                                    request_data={"product_title": product.title, "price": str(product.extracted_price)},
                                    response_summary={"url": store_result.url, "domain": store_result.domain},
                                    product_link=store_result.url
                                )

                                # PASSO 2: Validações de URL
                                if search_provider._is_blocked_domain(store_result.domain):
                                    raise ValueError(f"BLOCKED_DOMAIN: {store_result.domain}")

                                if search_provider._is_foreign_domain(store_result.domain):
                                    raise ValueError(f"FOREIGN_DOMAIN: {store_result.domain}")

                                if search_provider._is_listing_url(store_result.url):
                                    raise ValueError(f"LISTING_URL: {store_result.url[:50]}")

                                if store_result.url in urls_seen:
                                    raise ValueError(f"DUPLICATE_URL: {store_result.url[:50]}")

                                # PASSO 3: Capturar screenshot e extrair preço
                                screenshot_filename = f"screenshot_{quote_request_id}_{len(valid_sources)}.png"
                                screenshot_path = os.path.join(settings.STORAGE_PATH, "screenshots", screenshot_filename)
                                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

                                price, method = await extractor.extract_price_and_screenshot(
                                    store_result.url, screenshot_path
                                )

                                if not price or price <= Decimal("1"):
                                    raise ValueError(f"EXTRACTION_ERROR: preço inválido {price}")

                                # Rejeitar preços absurdamente altos (provavelmente erro de parsing)
                                if price > Decimal("10000000"):  # > 10 milhões
                                    raise ValueError(f"EXTRACTION_ERROR: preço absurdo R$ {price} (provável erro de parsing)")

                                # PASSO 4: Validar PRICE_MISMATCH (se habilitado)
                                google_price = product.extracted_price
                                if enable_price_mismatch and google_price and google_price > 0:
                                    if not prices_match(float(price), float(google_price)):
                                        price_diff = abs(float(price) - float(google_price)) / float(google_price) * 100
                                        raise ValueError(f"PRICE_MISMATCH: Site R$ {price} vs Google R$ {google_price} (diff: {price_diff:.1f}%)")

                                # ✅ SUCESSO - Produto validado!
                                urls_seen.add(store_result.url)

                                screenshot_file = File(
                                    type=FileType.SCREENSHOT,
                                    mime_type="image/png",
                                    storage_path=screenshot_path,
                                    sha256=_calculate_sha256(screenshot_path)
                                )
                                db.add(screenshot_file)
                                db.flush()

                                # Determinar preço final:
                                # - Se enable_price_mismatch=True: usar preço extraído do site
                                # - Se enable_price_mismatch=False: usar preço do Google (consistente com seleção de bloco)
                                final_price = price if enable_price_mismatch else Decimal(str(google_price))

                                source = QuoteSource(
                                    quote_request_id=quote_request_id,
                                    url=store_result.url,
                                    domain=store_result.domain,
                                    page_title=product.title,
                                    price_value=final_price,
                                    currency="BRL",
                                    extraction_method=method,
                                    screenshot_file_id=screenshot_file.id,
                                    is_accepted=True
                                )
                                db.add(source)
                                valid_sources.append(source)
                                valid_sources_by_product_key[product_key] = source
                                validated_product_keys.add(product_key)

                                price_source_info = "" if enable_price_mismatch else " (preço Google)"
                                logger.info(f"  ✓ Validado [{len(validated_product_keys & block_keys)}/{num_quotes}]: {store_result.domain} - R$ {final_price}{price_source_info}")

                                # Registrar teste bem-sucedido
                                test_record["result"] = "success"
                                test_record["extracted_price"] = float(price)
                                test_record["final_price"] = float(final_price)
                                test_record["domain"] = store_result.domain
                                block_record["tests"].append(test_record)

                                search_stats["successful_products"].append({
                                    "title": product.title,
                                    "source": product.source,
                                    "google_price": float(product.extracted_price) if product.extracted_price else None,
                                    "extracted_price": float(price),
                                    "final_price": float(final_price),
                                    "price_source": "site" if enable_price_mismatch else "google",
                                    "url": store_result.url,
                                    "domain": store_result.domain
                                })

                            except Exception as e:
                                # ❌ FALHA - Descartar produto (mas continuar testando os outros do bloco)
                                error_msg = str(e)
                                logger.error(f"  ✗ Falha: {error_msg[:100]}")
                                failed_product_keys.add(product_key)

                                # Determinar passo da falha
                                failure_step = "UNKNOWN"
                                if "NO_STORE_LINK" in error_msg:
                                    failure_step = "IMMERSIVE_API"
                                elif any(x in error_msg for x in ["BLOCKED_DOMAIN", "FOREIGN_DOMAIN", "LISTING_URL", "DUPLICATE"]):
                                    failure_step = "URL_VALIDATION"
                                elif "EXTRACTION_ERROR" in error_msg:
                                    failure_step = "PRICE_EXTRACTION"
                                elif "PRICE_MISMATCH" in error_msg:
                                    failure_step = "PRICE_VALIDATION"

                                # Registrar teste falho
                                test_record["result"] = "failed"
                                test_record["failure_step"] = failure_step
                                test_record["error_message"] = error_msg[:100]
                                if 'store_result' in dir() and store_result:
                                    test_record["domain"] = store_result.domain
                                block_record["tests"].append(test_record)

                                search_stats["validation_failures"].append({
                                    "title": product.title,
                                    "source": product.source,
                                    "google_price": float(product.extracted_price) if product.extracted_price else None,
                                    "url": store_result.url if 'store_result' in dir() and store_result else "",
                                    "domain": store_result.domain if 'store_result' in dir() and store_result else "",
                                    "failure_step": failure_step,
                                    "error_message": error_msg[:200]
                                })

                                # Registrar falha no banco
                                try:
                                    failure_reason = CaptureFailureReason.OTHER
                                    if "NO_STORE_LINK" in error_msg:
                                        failure_reason = CaptureFailureReason.NO_STORE_LINK
                                    elif "BLOCKED_DOMAIN" in error_msg:
                                        failure_reason = CaptureFailureReason.BLOCKED_DOMAIN
                                    elif "FOREIGN_DOMAIN" in error_msg:
                                        failure_reason = CaptureFailureReason.FOREIGN_DOMAIN
                                    elif "LISTING_URL" in error_msg:
                                        failure_reason = CaptureFailureReason.LISTING_URL
                                    elif "URL_DUPLICADA" in error_msg or "DUPLICATE" in error_msg:
                                        failure_reason = CaptureFailureReason.DUPLICATE_URL
                                    elif "PRICE_MISMATCH" in error_msg:
                                        failure_reason = CaptureFailureReason.PRICE_MISMATCH
                                    elif "EXTRACTION" in error_msg or "INVALID_PRICE" in error_msg:
                                        failure_reason = CaptureFailureReason.INVALID_PRICE

                                    # Sanitizar preços para evitar overflow no banco (max 10^10)
                                    MAX_PRICE = Decimal("9999999999.99")
                                    safe_google_price = None
                                    if product.extracted_price:
                                        gp = Decimal(str(product.extracted_price))
                                        safe_google_price = min(gp, MAX_PRICE) if gp > 0 else None

                                    failure_record = QuoteSourceFailure(
                                        quote_request_id=quote_request_id,
                                        url=store_result.url if 'store_result' in dir() and store_result else f"product:{product.source}",
                                        domain=store_result.domain if 'store_result' in dir() and store_result else product.source,
                                        product_title=product.title,
                                        google_price=safe_google_price,
                                        failure_reason=failure_reason,
                                        error_message=error_msg[:1000]
                                    )
                                    db.add(failure_record)
                                    db.flush()
                                except Exception as save_error:
                                    logger.warning(f"Erro ao salvar falha: {save_error}")
                                    db.rollback()  # Rollback para continuar processamento

                                # NÃO sair do loop - continuar testando outros produtos do bloco

                        # Fim do for - todos os produtos do bloco foram testados
                        # Verificar resultado final deste bloco
                        valid_in_block_final = len(validated_product_keys & block_keys)

                        if valid_in_block_final >= num_quotes:
                            logger.info(f"✅ SUCESSO! {valid_in_block_final} cotações válidas no bloco")
                            block_record["result"] = "success"
                            search_stats["block_history"].append(block_record)

                            # Filtrar fontes para manter apenas as do bloco vencedor
                            valid_sources = [
                                s for pk, s in valid_sources_by_product_key.items()
                                if pk in block_keys
                            ]

                            # Marcar como não aceitas as fontes fora do bloco vencedor
                            for pk, source in valid_sources_by_product_key.items():
                                if pk not in block_keys:
                                    source.is_accepted = False
                                    logger.info(f"  Fonte {source.domain} marcada como não aceita (fora do bloco vencedor)")

                            return

                        # BLOCO FALHOU: testamos todos os produtos e temos < N válidos
                        # Recalcular blocos (produtos falhos serão excluídos)
                        block_record["result"] = "failed"
                        block_record["final_valid_count"] = valid_in_block_final
                        search_stats["block_history"].append(block_record)
                        logger.info(
                            f"  ❌ BLOCO FALHOU: apenas {valid_in_block_final}/{num_quotes} válidos após testar todos os produtos. "
                            f"Recalculando blocos..."
                        )

                    # Fim do while interno - não conseguiu neste nível de tolerância
                    logger.info(f"Tolerância {current_var_max*100:.0f}% esgotada após {global_iteration} iterações")

                # Se chegou aqui, não conseguiu mesmo com todos os fallbacks
                # Encontrar o bloco com mais validados para usar como "melhor esforço"
                total_validated = len(validated_product_keys)
                logger.warning(
                    f"Não foi possível obter {num_quotes} cotações em um único bloco. "
                    f"Total validado: {total_validated}. Tolerância final: {current_var_max*100:.0f}%"
                )

                # Selecionar o melhor bloco (com mais validados) do histórico
                # Recalcular usando validated_product_keys atual (não o status salvo no momento)
                best_block_keys = set()
                best_valid_count = 0

                for block_record in search_stats["block_history"]:
                    products = block_record.get("products_in_block", [])
                    block_product_keys = set()

                    for p in products:
                        pk = _make_product_key(p.get("title", ""), p.get("price", 0))
                        block_product_keys.add(pk)

                    # Contar quantos validados estão NESTE bloco
                    valid_count = len(validated_product_keys & block_product_keys)

                    if valid_count > best_valid_count:
                        best_valid_count = valid_count
                        best_block_keys = block_product_keys

                if best_block_keys and best_valid_count > 0:
                    logger.info(f"Selecionando melhor bloco com {best_valid_count} validados como fallback")

                    # Filtrar para manter apenas as do melhor bloco
                    valid_sources = [
                        s for pk, s in valid_sources_by_product_key.items()
                        if pk in best_block_keys
                    ]

                    # Marcar como não aceitas as fontes fora do melhor bloco
                    for pk, source in valid_sources_by_product_key.items():
                        if pk not in best_block_keys:
                            source.is_accepted = False
                            logger.info(f"  Fonte {source.domain} marcada como não aceita (fora do melhor bloco)")

        # Executar a lógica apropriada baseado na configuração de validação de preço
        # Usar try/finally para garantir que search_stats sejam salvos mesmo em caso de erro
        extraction_error = None
        try:
            if enable_price_mismatch:
                # Fluxo COM validação de preço (extrai preço do site e compara com Google)
                logger.info("Usando fluxo COM validação de preço (extract_prices_with_blocks)")
                asyncio.run(extract_prices_with_blocks())
            else:
                # Fluxo SEM validação de preço (usa apenas preço do Google Shopping)
                logger.info("Usando fluxo SEM validação de preço (extract_prices_google_only)")
                asyncio.run(extract_prices_google_only())
        except Exception as e:
            extraction_error = e
            logger.error(f"Erro durante extração de preços: {str(e)}")
        finally:
            # Salvar estatísticas detalhadas de busca no JSON da cotação (sempre, mesmo com erro)
            if quote_request.google_shopping_response_json:
                quote_request.google_shopping_response_json["search_stats"] = search_stats
                quote_request.google_shopping_response_json["search_stats"]["final_valid_sources"] = len(valid_sources)
                quote_request.google_shopping_response_json["search_stats"]["final_failed_products"] = len(failed_product_keys)
                quote_request.google_shopping_response_json["search_stats"]["extraction_error"] = str(extraction_error) if extraction_error else None
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(quote_request, "google_shopping_response_json")
                db.commit()

        # Re-lançar a exceção se houve erro
        if extraction_error:
            raise extraction_error

        logger.info(f"Extracted {len(valid_sources)} valid prices")
        logger.info(f"Search stats: products_tested={search_stats['products_tested']}, blocks_recalculated={search_stats['blocks_recalculated']}, immersive_api_calls={search_stats['immersive_api_calls']}")

        # Calculando estatísticas
        _update_progress(db, quote_request, "calculating_stats", 80, f"Analisando {len(valid_sources)} preços coletados e calculando média...")

        # Registrar custo do SERPAPI (1 chamada por cotação)
        _register_serpapi_cost(db, quote_request, num_api_calls=1)

        if not valid_sources:
            raise ValueError("No valid prices found")

        db.commit()

        # Usar todas as cotações válidas aceitas
        accepted_sources = [s for s in valid_sources if s.is_accepted]

        if accepted_sources:
            prices = [s.price_value for s in accepted_sources]
            quote_request.valor_medio = sum(prices) / len(prices)
            quote_request.valor_minimo = min(prices)
            quote_request.valor_maximo = max(prices)

            # Calcular variação: (MAX / MIN - 1) * 100
            if quote_request.valor_minimo > 0:
                variacao = (quote_request.valor_maximo / quote_request.valor_minimo - 1) * 100
                quote_request.variacao_percentual = variacao
                logger.info(f"Variação calculada: {variacao:.2f}%")
        else:
            prices = [s.price_value for s in valid_sources]
            quote_request.valor_medio = sum(prices) / len(prices)
            quote_request.valor_minimo = min(prices)
            quote_request.valor_maximo = max(prices)

            # Calcular variação
            if quote_request.valor_minimo > 0:
                variacao = (quote_request.valor_maximo / quote_request.valor_minimo - 1) * 100
                quote_request.variacao_percentual = variacao

        # ========================================
        # CHECKPOINT: Marcar início da finalização
        # ========================================
        checkpoint_mgr.save_checkpoint(quote_request, ProcessingCheckpoint.FINALIZATION, progress_percentage=90)

        # Finalizando
        _update_progress(db, quote_request, "finalizing", 95, "Salvando resultados e finalizando cotação...")

        # Determinar status final baseado na quantidade de fontes
        # RN06: fontes >= N → DONE, 0 < fontes < N → AWAITING_REVIEW
        num_accepted = len(accepted_sources) if accepted_sources else len(valid_sources)

        if num_accepted >= num_quotes:
            quote_request.status = QuoteStatus.DONE
            quote_request.current_step = "completed"
            quote_request.step_details = f"Cotação concluída! {num_accepted} fontes de preço obtidas."
            logger.info(f"Quote request {quote_request_id} completed successfully (DONE). {num_accepted}/{num_quotes} sources.")
        else:
            quote_request.status = QuoteStatus.AWAITING_REVIEW
            quote_request.current_step = "awaiting_review"
            quote_request.step_details = f"Cotação com {num_accepted} fontes (mínimo esperado: {num_quotes}). Requer revisão."
            logger.warning(f"Quote request {quote_request_id} completed with insufficient sources (AWAITING_REVIEW). {num_accepted}/{num_quotes} sources.")

        quote_request.progress_percentage = 100
        db.commit()
        db.refresh(quote_request)

        # ========================================
        # CHECKPOINT: Marcar processamento concluído
        # ========================================
        checkpoint_mgr.complete_processing(quote_request, quote_request.status)

        logger.info(f"Quote request {quote_request_id} finalized. Average price: R$ {quote_request.valor_medio}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing quote request {quote_request_id}: {error_msg}")

        # Rollback de transações pendentes antes de atualizar o status
        db.rollback()

        # Recarregar quote_request após rollback
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if quote_request:
            # Não sobrescrever status se já foi cancelado pelo usuário
            if quote_request.status == QuoteStatus.CANCELLED:
                logger.info(f"Quote {quote_request_id} was cancelled by user, keeping CANCELLED status")
            else:
                # Tratar rate limit especificamente
                if "rate_limit_error" in error_msg or "429" in error_msg:
                    quote_request.current_step = "rate_limited"
                    quote_request.step_details = "Limite de taxa da API atingido. Aguarde alguns minutos e tente novamente."
                else:
                    quote_request.current_step = "error"
                    quote_request.step_details = f"Erro: {error_msg[:500]}"

                quote_request.status = QuoteStatus.ERROR
                quote_request.error_message = error_msg[:1000]  # Limitar tamanho
                db.commit()

        raise

    finally:
        db.close()


def _get_integration_setting(db: Session, provider: str, key: str) -> Optional[str]:
    from app.models.integration_setting import IntegrationSetting
    from app.core.security import decrypt_value

    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()

    if integration and integration.settings_json.get(key):
        encrypted_value = integration.settings_json.get(key)
        try:
            return decrypt_value(encrypted_value)
        except:
            return encrypted_value

    return None


def _get_integration_other_setting(db: Session, provider: str, key: str) -> Optional[str]:
    """Get a non-encrypted setting from integration settings (like model selection)"""
    from app.models.integration_setting import IntegrationSetting

    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()

    if integration and integration.settings_json.get(key):
        return integration.settings_json.get(key)

    return None


def _get_parameter(db: Session, key: str, default, config_version_id: int = None):
    """
    Busca parâmetros na seguinte ordem de prioridade:
    1. Configuração do projeto (se config_version_id fornecido)
    2. Parâmetros globais do sistema
    3. Valor default
    """
    from app.models.settings import Setting
    from app.models.project_config import ProjectConfigVersion

    # Primeiro, tentar buscar da configuração do projeto
    if config_version_id:
        config_version = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.id == config_version_id
        ).first()
        if config_version:
            # Mapear keys para campos do ProjectConfigVersion
            field_mapping = {
                "numero_cotacoes_por_pesquisa": config_version.numero_cotacoes_por_pesquisa,
                "variacao_maxima_percent": float(config_version.variacao_maxima_percent) if config_version.variacao_maxima_percent else None,
                "pesquisador_padrao": config_version.pesquisador_padrao,
                "local_padrao": config_version.local_padrao,
                "serpapi_location": config_version.serpapi_location,
                "enable_price_mismatch_validation": config_version.enable_price_mismatch_validation if hasattr(config_version, 'enable_price_mismatch_validation') else True,
            }
            if key in field_mapping and field_mapping[key] is not None:
                logger.info(f"Using project config parameter {key}={field_mapping[key]} from config_version_id={config_version_id}")
                return field_mapping[key]

    # Fallback para parâmetros globais
    setting = db.query(Setting).filter(Setting.key == "parameters").first()
    if setting and setting.value_json.get(key) is not None:
        return setting.value_json[key]
    return default




def _calculate_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _register_ai_cost(db: Session, quote_request: QuoteRequest, model: str, tokens_used: int, ai_provider: str = "anthropic"):
    """Registra o custo de uma chamada à API de IA (Anthropic ou OpenAI)"""
    try:
        api_name = 'openai' if ai_provider == 'openai' else 'anthropic'

        # Buscar configuração ativa de custo por token para o modelo (ou qualquer modelo do provedor ativo)
        cost_config = db.query(ApiCostConfig).filter(
            and_(
                ApiCostConfig.api_name == api_name,
                ApiCostConfig.is_active == True
            )
        ).filter(
            (ApiCostConfig.model_name == model) | (ApiCostConfig.model_name.is_(None))
        ).first()

        if not cost_config or not cost_config.cost_per_token_brl:
            logger.warning(f"Nenhuma configuração de custo encontrada para {api_name} modelo {model}")
            return

        # Calcular custo total
        unit_cost = cost_config.cost_per_token_brl
        total_cost = Decimal(str(tokens_used)) * unit_cost

        # Carregar relacionamentos se necessário
        client_name = None
        project_name = None

        # QuoteRequest tem project_id, não client_id direto
        # Buscar cliente através do projeto
        if quote_request.project_id:
            from app.models import Project
            project = db.query(Project).filter(Project.id == quote_request.project_id).first()
            if project:
                project_name = project.name
                if project.client_id:
                    from app.models import Client
                    client = db.query(Client).filter(Client.id == project.client_id).first()
                    if client:
                        client_name = client.name

        # Criar transação financeira
        transaction = FinancialTransaction(
            api_name=api_name,
            quote_id=quote_request.id,
            client_name=client_name,
            project_id=quote_request.project_id,
            project_name=project_name,
            user_id=None,  # QuoteRequest não tem user_id
            user_name=None,
            description=f"Análise de item - {tokens_used} tokens ({model})",
            quantity=tokens_used,
            unit_cost_brl=unit_cost,
            total_cost_brl=total_cost
        )

        db.add(transaction)
        db.commit()

        logger.info(f"Custo {api_name.upper()} registrado: {tokens_used} tokens x R$ {unit_cost} = R$ {total_cost}")

    except Exception as e:
        logger.error(f"Erro ao registrar custo de IA: {e}")
        db.rollback()


def _register_anthropic_cost(db: Session, quote_request: QuoteRequest, model: str, tokens_used: int):
    """Registra o custo de uma chamada à API Anthropic (wrapper para retrocompatibilidade)"""
    try:
        # Buscar configuração ativa de custo por token para o modelo (ou qualquer modelo anthropic ativo)
        cost_config = db.query(ApiCostConfig).filter(
            and_(
                ApiCostConfig.api_name == 'anthropic',
                ApiCostConfig.is_active == True
            )
        ).filter(
            (ApiCostConfig.model_name == model) | (ApiCostConfig.model_name.is_(None))
        ).first()

        if not cost_config or not cost_config.cost_per_token_brl:
            logger.warning(f"Nenhuma configuração de custo encontrada para Anthropic modelo {model}")
            return

        # Calcular custo total
        unit_cost = cost_config.cost_per_token_brl
        total_cost = Decimal(str(tokens_used)) * unit_cost

        # Carregar relacionamentos se necessário
        client_name = None
        project_name = None

        # QuoteRequest tem project_id, não client_id direto
        # Buscar cliente através do projeto
        if quote_request.project_id:
            from app.models import Project
            project = db.query(Project).filter(Project.id == quote_request.project_id).first()
            if project:
                project_name = project.name
                if project.client_id:
                    from app.models import Client
                    client = db.query(Client).filter(Client.id == project.client_id).first()
                    if client:
                        client_name = client.name

        # Criar transação financeira
        transaction = FinancialTransaction(
            api_name='anthropic',
            quote_id=quote_request.id,
            client_name=client_name,
            project_id=quote_request.project_id,
            project_name=project_name,
            user_id=None,  # QuoteRequest não tem user_id
            user_name=None,
            description=f"Análise de item - {tokens_used} tokens ({model})",
            quantity=tokens_used,
            unit_cost_brl=unit_cost,
            total_cost_brl=total_cost
        )

        db.add(transaction)
        db.commit()

        logger.info(f"Custo Anthropic registrado: {tokens_used} tokens x R$ {unit_cost} = R$ {total_cost}")

    except Exception as e:
        logger.error(f"Erro ao registrar custo Anthropic: {e}")
        db.rollback()


def _register_serpapi_cost(db: Session, quote_request: QuoteRequest, num_api_calls: int = 1):
    """Registra o custo de chamadas à API SERPAPI"""
    try:
        # Buscar configuração ativa de custo por chamada
        cost_config = db.query(ApiCostConfig).filter(
            and_(
                ApiCostConfig.api_name == 'serpapi',
                ApiCostConfig.is_active == True,
                ApiCostConfig.end_date >= datetime.now(timezone.utc)  # Período válido
            )
        ).first()

        if not cost_config or not cost_config.cost_per_call_brl:
            logger.warning("Nenhuma configuração de custo ativa encontrada para SERPAPI")
            return

        # Calcular custo total
        unit_cost = cost_config.cost_per_call_brl
        total_cost = Decimal(str(num_api_calls)) * unit_cost

        # Carregar relacionamentos se necessário
        client_name = None
        project_name = None

        # QuoteRequest tem project_id, não client_id direto
        # Buscar cliente através do projeto
        if quote_request.project_id:
            from app.models import Project
            project = db.query(Project).filter(Project.id == quote_request.project_id).first()
            if project:
                project_name = project.name
                if project.client_id:
                    from app.models import Client
                    client = db.query(Client).filter(Client.id == project.client_id).first()
                    if client:
                        client_name = client.name

        # Criar transação financeira
        transaction = FinancialTransaction(
            api_name='serpapi',
            quote_id=quote_request.id,
            client_name=client_name,
            project_id=quote_request.project_id,
            project_name=project_name,
            user_id=None,  # QuoteRequest não tem user_id
            user_name=None,
            description=f"Busca de preços - {num_api_calls} chamada(s)",
            quantity=num_api_calls,
            unit_cost_brl=unit_cost,
            total_cost_brl=total_cost
        )

        db.add(transaction)
        db.commit()

        logger.info(f"Custo SERPAPI registrado: {num_api_calls} chamadas x R$ {unit_cost} = R$ {total_cost}")

    except Exception as e:
        logger.error(f"Erro ao registrar custo SERPAPI: {e}")
        db.rollback()


def _process_fipe_quote(db: Session, quote_request: QuoteRequest, analysis_result) -> bool:
    """
    Processa cotação de veículo usando API FIPE.

    Fluxo otimizado (REQ-FIPE-003):
    1. Consulta Banco de Preços local primeiro
    2. Se encontrar cotação VIGENTE, reutiliza
    3. Se não encontrar ou EXPIRADA, consulta API FIPE
    4. Atualiza/cria registro no Banco de Preços (UPSERT)

    Returns:
        bool: True se deve usar fallback para Google Shopping, False se concluiu com sucesso
    """
    import asyncio
    from app.services.fipe_client import FipeClient
    from app.services.fipe_pdf_generator import FipePDFGenerator
    from app.models import VehiclePriceBank, Setting
    from dateutil.relativedelta import relativedelta

    try:
        fipe_params = analysis_result.fipe_api

        _update_progress(db, quote_request, "checking_price_bank", 45,
                        f"Verificando Banco de Preços de Veículos...")

        # ========== PASSO 1: Consultar Banco de Preços Local ==========
        # Obter parâmetro de vigência (default: 6 meses)
        vigencia_meses = 6
        setting = db.query(Setting).filter(Setting.key == "parameters").first()
        if setting and setting.value_json:
            vigencia_meses = setting.value_json.get("vigencia_cotacao_veiculos", 6)

        # Calcular data limite para vigência
        limite_vigencia = datetime.now() - relativedelta(months=vigencia_meses)

        # Extrair dados do veículo da análise da IA
        marca_busca = analysis_result.marca if hasattr(analysis_result, 'marca') else None
        modelo_busca = analysis_result.modelo if hasattr(analysis_result, 'modelo') else None
        ano_busca = None
        combustivel_busca = None

        if hasattr(analysis_result, 'especificacoes') and analysis_result.especificacoes:
            essenciais = analysis_result.especificacoes.get("essenciais", {})
            ano_busca = essenciais.get("ano_modelo")
            combustivel_busca = essenciais.get("combustivel")

        # Converter ano para inteiro se possível
        if ano_busca:
            try:
                ano_busca = int(str(ano_busca).strip())
            except (ValueError, TypeError):
                ano_busca = None

        logger.info(f"[FIPE] Buscando no banco de preços por semelhança: marca='{marca_busca}', modelo='{modelo_busca}', ano={ano_busca}, combustivel='{combustivel_busca}'")

        # Buscar no banco de preços por SEMELHANÇA (marca, modelo, ano, combustível)
        existing_price = None

        if marca_busca and modelo_busca:
            from sqlalchemy import func, or_

            # Query base com filtro de marca (case insensitive, match parcial)
            query = db.query(VehiclePriceBank).filter(
                VehiclePriceBank.brand_name.ilike(f"%{marca_busca}%")
            )

            # Filtro de modelo (match parcial)
            # Dividir o modelo em palavras e buscar por cada palavra-chave
            modelo_palavras = modelo_busca.split()
            for palavra in modelo_palavras:
                if len(palavra) >= 2:  # Ignorar palavras muito curtas
                    query = query.filter(VehiclePriceBank.model_name.ilike(f"%{palavra}%"))

            # Filtro de ano (exato)
            if ano_busca:
                query = query.filter(VehiclePriceBank.year_model == ano_busca)

            # Filtro de combustível (opcional, match parcial)
            if combustivel_busca and len(combustivel_busca) > 2:
                # Normalizar combustível para busca
                combustivel_norm = combustivel_busca.lower().strip()
                # Mapear variações comuns
                if "flex" in combustivel_norm:
                    query = query.filter(VehiclePriceBank.fuel_type.ilike("%flex%"))
                elif "diesel" in combustivel_norm:
                    query = query.filter(VehiclePriceBank.fuel_type.ilike("%diesel%"))
                elif "gasolina" in combustivel_norm:
                    query = query.filter(VehiclePriceBank.fuel_type.ilike("%gasolina%"))
                elif "alcool" in combustivel_norm or "etanol" in combustivel_norm:
                    query = query.filter(or_(
                        VehiclePriceBank.fuel_type.ilike("%alcool%"),
                        VehiclePriceBank.fuel_type.ilike("%etanol%")
                    ))

            # Ordenar por data de atualização (mais recente primeiro)
            existing_price = query.order_by(VehiclePriceBank.updated_at.desc()).first()

            if existing_price:
                logger.info(f"[FIPE] Encontrado no banco por semelhança: {existing_price.vehicle_name} (código {existing_price.codigo_fipe})")
            else:
                logger.info(f"[FIPE] Nenhum veículo encontrado no banco por semelhança")

        # Verificar se cotação está vigente
        if existing_price:
            updated_at = existing_price.updated_at
            if updated_at and updated_at.tzinfo:
                updated_at = updated_at.replace(tzinfo=None)

            is_vigente = updated_at >= limite_vigencia if updated_at else False

            if is_vigente:
                logger.info(f"[FIPE] Reutilizando cotação VIGENTE do banco de preços: {existing_price.vehicle_name} - R$ {existing_price.price_value}")
                _update_progress(db, quote_request, "using_cached_price", 60,
                                f"Utilizando cotação vigente do banco de preços: R$ {existing_price.price_value:,.2f}")

                # Usar cotação existente - criar QuoteSource
                from app.models.quote_source import ExtractionMethod

                fipe_source = QuoteSource(
                    quote_request_id=quote_request.id,
                    url=f"https://veiculos.fipe.org.br/?codigoTipoVeiculo={existing_price.vehicle_type}&codigoFipe={existing_price.codigo_fipe}",
                    domain="fipe.org.br",
                    page_title=f"Tabela FIPE - {existing_price.vehicle_name} (Banco de Preços)",
                    price_value=existing_price.price_value,
                    currency="BRL",
                    extraction_method=ExtractionMethod.API_FIPE,
                    is_accepted=True,
                    screenshot_file_id=existing_price.screenshot_file_id  # Usar screenshot do cache
                )
                db.add(fipe_source)
                db.flush()

                # Log se screenshot está disponível ou não
                if existing_price.screenshot_file_id:
                    logger.info(f"[FIPE] Usando screenshot do cache: file_id={existing_price.screenshot_file_id}")
                else:
                    logger.warning(f"[FIPE] Cache sem screenshot disponível para {existing_price.vehicle_name}")

                # Salvar resultado no JSON da cotação
                import copy
                from sqlalchemy.orm.attributes import flag_modified
                payload = copy.deepcopy(quote_request.claude_payload_json or {})
                payload["fipe_result"] = {
                    "success": True,
                    "source": "price_bank",
                    "api_calls": 0,
                    "vehicle_name": existing_price.vehicle_name,
                    "codigo_fipe": existing_price.codigo_fipe,
                    "price": {
                        "price": f"R$ {existing_price.price_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        "price_value": float(existing_price.price_value),
                        "brand": existing_price.brand_name,
                        "model": existing_price.model_name,
                        "modelYear": existing_price.year_model,
                        "fuel": existing_price.fuel_type,
                        "codeFipe": existing_price.codigo_fipe,
                        "referenceMonth": existing_price.reference_month,
                        "vehicleType": existing_price.vehicle_type
                    }
                }
                quote_request.claude_payload_json = payload
                flag_modified(quote_request, "claude_payload_json")

                # Definir valores de preço
                quote_request.valor_medio = fipe_source.price_value
                quote_request.valor_minimo = fipe_source.price_value
                quote_request.valor_maximo = fipe_source.price_value
                quote_request.variacao_percentual = Decimal("0")

                # Registrar log de integração como Banco de Preço de Veículos
                bank_log = IntegrationLog(
                    quote_request_id=quote_request.id,
                    integration_type="vehicle_price_bank",
                    activity=f"Cotação do Banco de Preços de Veículos (vigente)",
                    response_summary={
                        "source": "vehicle_price_bank",
                        "success": True,
                        "api_calls": 0,
                        "vehicle_name": existing_price.vehicle_name,
                        "codigo_fipe": existing_price.codigo_fipe,
                        "brand_name": existing_price.brand_name,
                        "model_name": existing_price.model_name,
                        "year_model": existing_price.year_model,
                        "fuel_type": existing_price.fuel_type,
                        "reference_month": existing_price.reference_month,
                        "cached_at": existing_price.updated_at.isoformat() if existing_price.updated_at else None,
                        "screenshot_path": existing_price.screenshot_path,
                        "price": {
                            "price": f"R$ {existing_price.price_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                            "price_value": float(existing_price.price_value),
                            "brand": existing_price.brand_name,
                            "model": existing_price.model_name,
                            "modelYear": existing_price.year_model,
                            "fuel": existing_price.fuel_type,
                            "codeFipe": existing_price.codigo_fipe,
                            "referenceMonth": existing_price.reference_month,
                            "vehicleType": existing_price.vehicle_type
                        }
                    }
                )
                db.add(bank_log)

                # Finalizar cotação
                _update_progress(db, quote_request, "finalizing", 95, "Finalizando cotação...")

                quote_request.status = QuoteStatus.DONE
                quote_request.current_step = "completed"
                quote_request.step_details = f"Cotação concluída via Banco de Preços! Valor: R$ {existing_price.price_value:,.2f}"
                quote_request.progress_percentage = 100

                db.commit()
                db.refresh(quote_request)

                # Gerar PDF (usando screenshot do cache se disponível)
                _generate_fipe_pdf(db, quote_request, fipe_source, existing_price)

                logger.info(f"[FIPE] Quote {quote_request.id} completed from cache. Price: R$ {existing_price.price_value}")
                return False  # Concluído com sucesso
            else:
                logger.info(f"[FIPE] Cotação EXPIRADA ({(datetime.now() - updated_at).days} dias). Atualizando via API FIPE...")

        _update_progress(db, quote_request, "searching_fipe", 50,
                        f"Consultando Tabela FIPE para {analysis_result.marca} {analysis_result.modelo}...")

        # Criar cliente FIPE
        fipe_client = FipeClient()

        # Extrair ano modelo e combustivel (texto) do retorno da IA
        ano_modelo = None
        combustivel = None
        if hasattr(analysis_result, 'especificacoes') and analysis_result.especificacoes:
            essenciais = analysis_result.especificacoes.get("essenciais", {})
            ano_modelo = str(essenciais.get("ano_modelo", "")) if essenciais.get("ano_modelo") else None
            combustivel = essenciais.get("combustivel", "")

        logger.info(f"[FIPE] Dados da IA - Ano: {ano_modelo}, Combustível: {combustivel}")

        # Executar busca na FIPE com fluxo OTIMIZADO
        # Novo fluxo: brands -> years -> models -> price
        async def search_fipe():
            # Enriquecer busca_modelo com o modelo completo do analysis_result
            busca_modelo = fipe_params.busca_modelo.copy() if fipe_params.busca_modelo else {}

            # Se analysis_result.modelo existir e for diferente do termo_principal, adicionar como variação
            modelo_completo = analysis_result.modelo if hasattr(analysis_result, 'modelo') else None
            if modelo_completo:
                # Garantir que o modelo completo esteja nas variações
                variacoes = list(busca_modelo.get('variacoes', []))
                if modelo_completo not in variacoes and modelo_completo != busca_modelo.get('termo_principal'):
                    variacoes.append(modelo_completo)
                busca_modelo['variacoes'] = variacoes

                # Se termo_principal for muito curto (ex: "ASX"), usar o modelo completo como termo principal
                termo_principal = busca_modelo.get('termo_principal', '')
                if len(termo_principal) < len(modelo_completo) and len(termo_principal.split()) <= 1:
                    busca_modelo['termo_principal'] = modelo_completo
                    logger.info(f"[FIPE] Usando modelo completo como termo principal: {modelo_completo}")

            return await fipe_client.search_vehicle_optimized(
                vehicle_type=fipe_params.vehicle_type,
                busca_marca=fipe_params.busca_marca or {},
                busca_modelo=busca_modelo,
                year_id_estimado=fipe_params.year_id_estimado,
                ano_modelo=ano_modelo,
                combustivel=combustivel
            )

        fipe_result = asyncio.run(search_fipe())

        logger.info(f"FIPE search result: success={fipe_result.success}, api_calls={fipe_result.api_calls}")

        # Salvar resultado FIPE no JSON da cotação
        fipe_data = {
            "success": fipe_result.success,
            "api_calls": fipe_result.api_calls,
            "search_path": fipe_result.search_path,
            "brand_id": fipe_result.brand_id,
            "brand_name": fipe_result.brand_name,
            "model_id": fipe_result.model_id,
            "model_name": fipe_result.model_name,
            "year_id": fipe_result.year_id,
            "error_message": fipe_result.error_message
        }

        if fipe_result.price:
            fipe_data["price"] = {
                "price": fipe_result.price.price,
                "price_value": fipe_result.price.price_value,
                "brand": fipe_result.price.brand,
                "model": fipe_result.price.model,
                "modelYear": fipe_result.price.modelYear,
                "fuel": fipe_result.price.fuel,
                "codeFipe": fipe_result.price.codeFipe,
                "referenceMonth": fipe_result.price.referenceMonth,
                "vehicleType": fipe_result.price.vehicleType,
                "fuelAcronym": fipe_result.price.fuelAcronym
            }

        # Atualizar claude_payload_json com dados da FIPE
        # Usar copia para garantir que SQLAlchemy detecte a mudanca
        import copy
        from sqlalchemy.orm.attributes import flag_modified
        payload = copy.deepcopy(quote_request.claude_payload_json or {})
        payload["fipe_result"] = fipe_data
        quote_request.claude_payload_json = payload
        flag_modified(quote_request, "claude_payload_json")
        db.commit()

        if not fipe_result.success:
            # FIPE falhou - tentar fallback para Google Shopping se disponível
            fallback_query = ""
            if analysis_result.fallback_google_shopping:
                fallback_query = analysis_result.fallback_google_shopping.get("query_principal", "")

            if fallback_query and fallback_query.strip():
                logger.warning(f"FIPE search failed: {fipe_result.error_message}. Trying Google Shopping fallback with query: {fallback_query}")
                quote_request.error_message = f"FIPE: {fipe_result.error_message}. Tentando Google Shopping..."
                db.commit()
                # Alterar query para usar fallback
                analysis_result.query_principal = fallback_query
                # Retornar True para continuar com fluxo normal (Google Shopping)
                return True
            else:
                # Sem fallback válido - criar query baseada nos dados do veículo
                marca = analysis_result.bem_patrimonial.get("marca", "") if analysis_result.bem_patrimonial else ""
                modelo = analysis_result.bem_patrimonial.get("modelo", "") if analysis_result.bem_patrimonial else ""
                if marca and modelo:
                    fallback_query = f"{marca} {modelo} preço"
                    logger.warning(f"FIPE failed, no fallback. Generated query from vehicle data: {fallback_query}")
                    quote_request.error_message = f"FIPE: {fipe_result.error_message}. Usando busca genérica..."
                    db.commit()
                    analysis_result.query_principal = fallback_query
                    return True
                else:
                    raise ValueError(f"Consulta FIPE falhou e não há dados suficientes para busca alternativa: {fipe_result.error_message}")

        _update_progress(db, quote_request, "processing_fipe_result", 70,
                        f"Preço FIPE encontrado: {fipe_result.price.price}")

        # Criar fonte de preço (QuoteSource) com dados da FIPE
        from app.models.quote_source import ExtractionMethod

        fipe_source = QuoteSource(
            quote_request_id=quote_request.id,
            url=f"https://veiculos.fipe.org.br/?codigoTipoVeiculo={fipe_result.price.vehicleType}&codigoFipe={fipe_result.price.codeFipe}",
            domain="fipe.org.br",
            page_title=f"Tabela FIPE - {fipe_result.price.brand} {fipe_result.price.model} {fipe_result.price.modelYear}",
            price_value=Decimal(str(fipe_result.price.price_value)),
            currency="BRL",
            extraction_method=ExtractionMethod.API_FIPE,
            is_accepted=True
        )
        db.add(fipe_source)
        db.flush()

        logger.info(f"Created FIPE source: {fipe_source.page_title} - R$ {fipe_source.price_value}")

        # Definir valores de preço
        quote_request.valor_medio = fipe_source.price_value
        quote_request.valor_minimo = fipe_source.price_value
        quote_request.valor_maximo = fipe_source.price_value
        quote_request.variacao_percentual = Decimal("0")

        _update_progress(db, quote_request, "capturing_screenshot", 75, "Capturando comprovação do site FIPE...")

        # Capturar screenshot do site FIPE para comprovação
        screenshot_path = None
        screenshot_file_id = None
        try:
            from app.services.fipe_screenshot import capture_fipe_screenshot

            # Extrair combustivel do resultado FIPE
            combustivel = fipe_result.price.fuel if fipe_result.price else "Gasolina"

            # Determinar tipo de veiculo
            vehicle_type_map = {1: "cars", 2: "motorcycles", 3: "trucks"}
            vtype = vehicle_type_map.get(fipe_result.price.vehicleType, "cars") if fipe_result.price else "cars"

            screenshot_path = asyncio.run(capture_fipe_screenshot(
                codigo_fipe=fipe_result.price.codeFipe,
                ano_modelo=fipe_result.price.modelYear,
                combustivel=combustivel,
                vehicle_type=vtype,
                quote_id=quote_request.id
            ))

            if screenshot_path:
                logger.info(f"Screenshot FIPE capturado: {screenshot_path}")
                # Criar registro de File para o screenshot
                screenshot_file = File(
                    type=FileType.SCREENSHOT,
                    mime_type="image/png",
                    storage_path=screenshot_path,
                    sha256=_calculate_sha256(screenshot_path)
                )
                db.add(screenshot_file)
                db.flush()
                screenshot_file_id = screenshot_file.id
                logger.info(f"Screenshot file registrado: ID={screenshot_file_id}")
            else:
                logger.warning("Screenshot FIPE não capturado (operação não bloqueante)")

        except Exception as screenshot_error:
            logger.warning(f"Erro ao capturar screenshot FIPE (não bloqueante): {screenshot_error}")

        _update_progress(db, quote_request, "saving_price_bank", 80, "Salvando no Banco de Preços de Veículos...")

        # Salvar/Atualizar no Banco de Precos de Veiculos (UPSERT - REQ-FIPE-003) com screenshot
        try:
            from app.models import VehiclePriceBank
            from datetime import date
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            # Parse reference month (ex: "dezembro de 2024" -> date(2024, 12, 1))
            months_map = {
                "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
                "abril": 4, "maio": 5, "junho": 6,
                "julho": 7, "agosto": 8, "setembro": 9,
                "outubro": 10, "novembro": 11, "dezembro": 12
            }
            ref_month_str = fipe_result.price.referenceMonth.lower()
            try:
                parts = ref_month_str.replace(" de ", " ").split()
                month_num = months_map.get(parts[0], 1)
                year_num = int(parts[1])
                ref_date = date(year_num, month_num, 1)
            except Exception:
                ref_date = date.today().replace(day=1)

            # Parse fuel code from year_id (ex: "2020-1" -> 1)
            fuel_code = 1
            if fipe_result.year_id and "-" in fipe_result.year_id:
                try:
                    fuel_code = int(fipe_result.year_id.split("-")[1])
                except Exception:
                    pass

            # Mapear fuel acronym para fuel type
            fuel_map = {"G": "Gasolina", "A": "Alcool", "D": "Diesel", "F": "Flex"}
            fuel_type = fuel_map.get(fipe_result.price.fuelAcronym, fipe_result.price.fuel or "Gasolina")

            # Mapear vehicle_type de inteiro para string (a API FIPE retorna inteiro mas espera string nas URLs)
            # vehicleType: 1=carro, 2=moto, 3=caminhão
            vehicle_type_int_to_str = {1: "cars", 2: "motorcycles", 3: "trucks"}
            vehicle_type_value = fipe_result.price.vehicleType
            if isinstance(vehicle_type_value, int):
                vehicle_type_str = vehicle_type_int_to_str.get(vehicle_type_value, "cars")
            else:
                vehicle_type_str = vehicle_type_value or "cars"

            # Dados para inserção/atualização (incluindo screenshot)
            vehicle_data = {
                "codigo_fipe": fipe_result.price.codeFipe,
                "year_id": fipe_result.year_id or "",
                "brand_id": int(fipe_result.brand_id) if fipe_result.brand_id else 0,
                "brand_name": fipe_result.price.brand,
                "model_id": int(fipe_result.model_id) if fipe_result.model_id else 0,
                "model_name": fipe_result.price.model,
                "year_model": fipe_result.price.modelYear,
                "fuel_type": fuel_type,
                "fuel_code": fuel_code,
                "vehicle_type": vehicle_type_str,
                "vehicle_name": f"{fipe_result.price.brand} {fipe_result.price.model} {fipe_result.price.modelYear}",
                "price_value": Decimal(str(fipe_result.price.price_value)),
                "reference_month": fipe_result.price.referenceMonth,
                "reference_date": ref_date,
                "quote_request_id": quote_request.id,
                "api_response_json": fipe_data.get("price"),
                "last_api_call": datetime.utcnow(),
                "screenshot_file_id": screenshot_file_id,
                "screenshot_path": screenshot_path,
                "has_screenshot": screenshot_file_id is not None  # Indica se tem screenshot válido
            }

            # UPSERT: INSERT ... ON CONFLICT (codigo_fipe, year_id) DO UPDATE
            stmt = pg_insert(VehiclePriceBank).values(**vehicle_data)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_vehicle_fipe_year',
                set_={
                    "brand_name": stmt.excluded.brand_name,
                    "model_name": stmt.excluded.model_name,
                    "price_value": stmt.excluded.price_value,
                    "reference_month": stmt.excluded.reference_month,
                    "reference_date": stmt.excluded.reference_date,
                    "quote_request_id": stmt.excluded.quote_request_id,
                    "api_response_json": stmt.excluded.api_response_json,
                    "last_api_call": stmt.excluded.last_api_call,
                    "screenshot_file_id": stmt.excluded.screenshot_file_id,
                    "screenshot_path": stmt.excluded.screenshot_path,
                    "has_screenshot": stmt.excluded.has_screenshot,
                    "updated_at": datetime.utcnow()
                }
            )
            db.execute(stmt)
            db.flush()
            logger.info(f"[FIPE] Banco de Preços atualizado (UPSERT): {vehicle_data['vehicle_name']} - R$ {vehicle_data['price_value']} (screenshot: {screenshot_path})")
        except Exception as vpb_error:
            logger.warning(f"Failed to save to VehiclePriceBank: {vpb_error}")

        _update_progress(db, quote_request, "generating_pdf", 90, "Gerando PDF da cotação FIPE...")

        # Gerar PDF da cotação FIPE
        try:
            pdf_generator = FipePDFGenerator()
            pdf_filename = f"cotacao_fipe_{quote_request.id}.pdf"
            pdf_path = os.path.join(settings.STORAGE_PATH, "documents", pdf_filename)
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

            pdf_generator.generate(
                output_path=pdf_path,
                quote_request=quote_request,
                fipe_result=fipe_result,
                analysis_result=analysis_result,
                screenshot_path=screenshot_path
            )

            # Registrar documento gerado
            pdf_file = File(
                type=FileType.GENERATED_DOCUMENT,
                mime_type="application/pdf",
                storage_path=pdf_path,
                sha256=_calculate_sha256(pdf_path)
            )
            db.add(pdf_file)
            db.flush()

            doc = GeneratedDocument(
                quote_request_id=quote_request.id,
                file_id=pdf_file.id,
                document_type="fipe_quote_pdf",
                title=f"Cotação Tabela FIPE - {fipe_result.price.brand} {fipe_result.price.model}"
            )
            db.add(doc)

            logger.info(f"Generated FIPE PDF: {pdf_path}")

        except Exception as pdf_error:
            logger.error(f"Error generating FIPE PDF: {pdf_error}")
            # Não falhar a cotação por erro no PDF

        # Registrar log de integração FIPE
        fipe_log = IntegrationLog(
            quote_request_id=quote_request.id,
            integration_type="fipe",
            activity=f"Consulta Tabela FIPE - {fipe_result.api_calls} chamadas",
            response_summary=fipe_data
        )
        db.add(fipe_log)

        # Finalizar cotação
        _update_progress(db, quote_request, "finalizing", 95, "Finalizando cotação FIPE...")

        quote_request.status = QuoteStatus.DONE
        quote_request.current_step = "completed"
        quote_request.step_details = f"Cotação FIPE concluída! Valor: {fipe_result.price.price}"
        quote_request.progress_percentage = 100

        db.commit()
        db.refresh(quote_request)

        logger.info(f"FIPE quote {quote_request.id} completed. Price: {fipe_result.price.price}")
        return False  # Sucesso - não precisa de fallback

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing FIPE quote {quote_request.id}: {error_msg}")

        db.rollback()

        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request.id).first()
        if quote_request and quote_request.status != QuoteStatus.CANCELLED:
            quote_request.status = QuoteStatus.ERROR
            quote_request.error_message = error_msg[:1000]
            quote_request.current_step = "error"
            quote_request.step_details = f"Erro FIPE: {error_msg[:500]}"
            db.commit()

        raise


def _generate_fipe_pdf(db: Session, quote_request: QuoteRequest, fipe_source: QuoteSource, vehicle_price):
    """
    Gera PDF para cotação FIPE usando dados do Banco de Preços (cache).
    Versão simplificada sem captura de screenshot.
    """
    from app.services.fipe_pdf_generator import FipePDFGenerator

    try:
        # Criar objeto FipeResult simulado para o gerador de PDF
        class CachedFipePrice:
            def __init__(self, vp):
                self.price = f"R$ {vp.price_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self.price_value = float(vp.price_value)
                self.brand = vp.brand_name
                self.model = vp.model_name
                self.modelYear = vp.year_model
                self.fuel = vp.fuel_type
                self.codeFipe = vp.codigo_fipe
                self.referenceMonth = vp.reference_month
                self.vehicleType = vp.vehicle_type
                self.fuelAcronym = vp.fuel_type[0].upper() if vp.fuel_type else "G"

        class CachedFipeResult:
            def __init__(self, vp):
                self.success = True
                self.price = CachedFipePrice(vp)
                self.api_calls = 0
                self.brand_id = vp.brand_id
                self.brand_name = vp.brand_name
                self.model_id = vp.model_id
                self.model_name = vp.model_name
                self.year_id = vp.year_id

        fipe_result = CachedFipeResult(vehicle_price)

        pdf_generator = FipePDFGenerator()
        pdf_filename = f"cotacao_fipe_{quote_request.id}.pdf"
        pdf_path = os.path.join(settings.STORAGE_PATH, "documents", pdf_filename)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        # Gerar PDF usando screenshot do cache se disponível
        cached_screenshot = vehicle_price.screenshot_path if hasattr(vehicle_price, 'screenshot_path') else None
        if cached_screenshot:
            # Verificar se o arquivo existe
            import os as os_check
            if not os_check.path.exists(cached_screenshot):
                logger.warning(f"Screenshot do cache não encontrado: {cached_screenshot}")
                cached_screenshot = None
            else:
                logger.info(f"Usando screenshot do cache: {cached_screenshot}")

        pdf_generator.generate(
            output_path=pdf_path,
            quote_request=quote_request,
            fipe_result=fipe_result,
            analysis_result=None,
            screenshot_path=cached_screenshot
        )

        # Registrar documento gerado
        pdf_file = File(
            type=FileType.GENERATED_DOCUMENT,
            mime_type="application/pdf",
            storage_path=pdf_path,
            sha256=_calculate_sha256(pdf_path)
        )
        db.add(pdf_file)
        db.flush()

        doc = GeneratedDocument(
            quote_request_id=quote_request.id,
            file_id=pdf_file.id,
            document_type="fipe_quote_pdf",
            title=f"Cotação Tabela FIPE - {vehicle_price.vehicle_name} (Banco de Preços)"
        )
        db.add(doc)
        db.commit()

        logger.info(f"Generated cached FIPE PDF: {pdf_path}")

    except Exception as pdf_error:
        logger.error(f"Error generating cached FIPE PDF: {pdf_error}")
        # Não falhar a cotação por erro no PDF
