from celery import Task
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import QuoteRequest, QuoteSource, File, GeneratedDocument, IntegrationLog, BlockedDomain
from app.models.quote_request import QuoteStatus
from app.models.file import FileType
from app.models.financial import ApiCostConfig, FinancialTransaction
from app.services.claude_client import ClaudeClient, FipeApiParams
from app.services.openai_client import OpenAIClient
from app.services.search_provider import SerpApiProvider, prices_match, PRICE_MISMATCH_TOLERANCE
from app.services.price_extractor import PriceExtractor
from app.services.pdf_generator import PDFGenerator
from app.services.fipe_client import FipeClient, FipeSearchResult
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

        # Iniciando processamento
        _update_progress(db, quote_request, "initializing", 5, "Carregando configurações e integrações...")

        # Determinar qual provedor de IA usar
        ai_provider = _get_integration_other_setting(db, "ANTHROPIC", "ai_provider")
        if not ai_provider:
            ai_provider = _get_integration_other_setting(db, "OPENAI", "ai_provider")
        if not ai_provider:
            ai_provider = settings.AI_PROVIDER  # default: "anthropic"

        logger.info(f"Using AI provider: {ai_provider}")

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

        # Preparando busca
        _update_progress(db, quote_request, "preparing_search", 40, "Preparando busca de preços em lojas online...")

        # Registrar custo da análise de IA (Anthropic ou OpenAI)
        if analysis_result.total_tokens_used > 0:
            _register_ai_cost(db, quote_request, model, analysis_result.total_tokens_used, ai_provider)

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

        logger.info(f"Quote {quote_request_id} using parameters: num_quotes={num_quotes}, variacao_maxima={variacao_maxima*100}%, config_version_id={config_version_id}")

        # Validar se a query foi gerada
        if not analysis_result.query_principal or not analysis_result.query_principal.strip():
            raise ValueError("Claude não conseguiu gerar uma query de busca válida. Verifique a descrição do item e tente novamente.")

        # Buscando produtos
        _update_progress(db, quote_request, "searching_products", 50, f"Buscando '{analysis_result.query_principal}' em marketplaces...")

        # Search products with variation filter
        # This optimizes API calls: 1 Shopping + N Immersive = N+1 total calls
        search_results, search_log = asyncio.run(
            search_provider.search_products(
                query=analysis_result.query_principal,
                limit=num_quotes,
                variacao_maxima=variacao_maxima
            )
        )

        logger.info(f"Found {len(search_results)} search results")
        logger.info(f"Search log: {search_log.model_dump_json()}")

        # Salvar resposta bruta do Google Shopping para consulta
        # Usar raw_shopping_response que contém o JSON original da API SerpAPI
        search_log_dict = search_log.model_dump()
        raw_response = search_log_dict.pop('raw_shopping_response', None)  # Remove from search_log to avoid duplication

        quote_request.google_shopping_response_json = {
            "raw_api_response": raw_response,  # JSON original da primeira chamada SerpAPI
            "processed_results": {
                "results_count": len(search_results),
                "products": [
                    {
                        "title": p.title,
                        "price": p.price,
                        "extracted_price": float(p.extracted_price) if p.extracted_price else None,
                        "store_name": p.store_name,
                        "domain": p.domain,
                        "url": p.url
                    } for p in search_results
                ]
            },
            "search_log": search_log_dict,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        db.commit()

        # Salvar o log detalhado da pesquisa no banco
        search_log_entry = IntegrationLog(
            quote_request_id=quote_request.id,
            integration_type="search_log",
            activity="Log detalhado da busca de produtos",
            response_summary=search_log.model_dump()
        )
        log_db = SessionLocal()
        try:
            log_db.add(search_log_entry)
            log_db.commit()
        except Exception as e:
            logger.error(f"Error saving search log: {e}")
            log_db.rollback()
        finally:
            log_db.close()

        # Registrar todas as chamadas da SerpAPI (Google Shopping + Immersive API)
        for api_call in search_provider.api_calls_made:
            log_serpapi_call(
                db=db,
                quote_request_id=quote_request.id,
                api_used=api_call["api_used"],
                search_url=api_call["search_url"],
                activity=api_call["activity"],
                request_data={"query": analysis_result.query_principal, "limit": num_quotes},
                response_summary={"results_found": len(search_results)} if api_call["api_used"] == "google_shopping" else None,
                product_link=api_call.get("product_link")
            )

        # Extraindo preços usando lógica de blocos com recálculo
        # Lógica:
        # 1. Manter produtos válidos na lista (participam do cálculo de blocos)
        # 2. Marcar produtos que falharam (remover da lista)
        # 3. Recalcular blocos após cada falha
        # 4. Priorizar blocos que contêm todos os produtos válidos
        # 5. Se não houver bloco com válidos e produtos suficientes:
        #    - Guardar válidos como "reserva"
        #    - Tentar novo bloco sem os produtos da reserva
        #    - Se novo bloco falhar, voltar para reserva
        # 6. Continuar até N resultados ou esgotar produtos
        _update_progress(db, quote_request, "extracting_prices", 60, f"Acessando {len(search_results)} lojas e capturando preços...")

        valid_sources = []
        valid_sources_by_url = {}  # {url: source} - para reutilização (URL única, não domínio)
        valid_prices = {}  # {url: price} - preços já validados por URL
        failed_urls = set()  # URLs que falharam (permite outros produtos do mesmo domínio)

        async def extract_prices_with_block_recalculation():
            """
            Lógica simplificada de extração com recálculo de bloco único:
            1. Calcula 1 bloco por vez baseado nos produtos disponíveis
            2. Se um produto falha, recalcula o bloco excluindo o produto
            3. Produtos já validados só participam do novo bloco se estiverem na faixa de variação
            4. Sistema de reserva: se o bloco atual não tem potencial, guarda resultado e tenta outro
            """
            from app.models.quote_source import ExtractionMethod
            nonlocal valid_sources, valid_sources_by_url, valid_prices, failed_urls

            all_products = list(search_results)
            iteration = 0
            max_iterations = 20

            # Sistema de reserva para quando precisamos tentar bloco alternativo
            reserve_sources = []
            reserve_sources_by_url = {}
            reserve_prices = {}
            has_reserve = False

            async with PriceExtractor() as extractor:
                while len(valid_sources) < num_quotes and iteration < max_iterations:
                    iteration += 1

                    # Construir lista de produtos disponíveis (excluir falhas)
                    available_products = [
                        p for p in all_products
                        if p.url not in failed_urls
                    ]

                    if not available_products:
                        logger.info(f"Iteration {iteration}: No products remaining")
                        break

                    # Ordenar por preço
                    available_products.sort(key=lambda p: float(p.extracted_price) if p.extracted_price else 0)

                    # Calcular UM bloco único
                    block = _calculate_best_block(
                        available_products,
                        valid_prices,
                        variacao_maxima,
                        num_quotes
                    )

                    if not block:
                        logger.info(f"Iteration {iteration}: No valid block could be created")
                        break

                    # Verificar quantos produtos validados estão no bloco
                    block_urls = {p.url for p in block}
                    valid_in_block = [url for url in valid_prices.keys() if url in block_urls]
                    valid_outside_block = [url for url in valid_prices.keys() if url not in block_urls]
                    untried_in_block = [p for p in block if p.url not in valid_prices and p.url not in failed_urls]
                    needed = num_quotes - len(valid_sources)

                    logger.info(
                        f"Iteration {iteration}: Block with {len(block)} products "
                        f"(R$ {block[0].extracted_price} - R$ {block[-1].extracted_price}), "
                        f"{len(valid_in_block)} valid in block, {len(valid_outside_block)} valid outside, "
                        f"{len(untried_in_block)} untried, need {needed} more"
                    )

                    # Se há validados fora do bloco, decidir o que fazer
                    if valid_outside_block and not has_reserve:
                        # Verificar se o bloco atual tem potencial para N cotações
                        potential = len(valid_in_block) + len(untried_in_block)
                        if potential < num_quotes:
                            # Bloco atual não tem potencial - guardar como reserva e tentar outro
                            logger.info(
                                f"  Block potential ({potential}) < required ({num_quotes}). "
                                f"Saving {len(valid_sources)} as reserve, trying fresh block."
                            )
                            reserve_sources = list(valid_sources)
                            reserve_sources_by_url = dict(valid_sources_by_url)
                            reserve_prices = dict(valid_prices)
                            has_reserve = True

                            # Limpar validados para tentar bloco fresco
                            valid_sources = []
                            valid_sources_by_url = {}
                            valid_prices = {}
                            continue

                    # Extrair preços dos produtos do bloco
                    new_failures = []

                    for product in block:
                        if len(valid_sources) >= num_quotes:
                            break

                        # Reutilizar válido
                        if product.url in valid_sources_by_url:
                            continue

                        if product.url in failed_urls:
                            continue

                        logger.info(f"    → Extracting: {product.domain} ({product.url[:60]}...)")

                        try:
                            screenshot_filename = f"screenshot_{quote_request_id}_{len(valid_sources)}.png"
                            screenshot_path = os.path.join(settings.STORAGE_PATH, "screenshots", screenshot_filename)
                            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

                            price, method = await extractor.extract_price_and_screenshot(
                                product.url,
                                screenshot_path
                            )

                            if price and price > Decimal("1"):
                                final_price = price
                                final_method = method
                                google_price = product.extracted_price

                                # Validar preço do site contra Google Shopping
                                if google_price and google_price > Decimal("0"):
                                    if not prices_match(float(price), float(google_price)):
                                        price_diff = abs(float(price) - float(google_price)) / float(google_price) * 100
                                        logger.warning(
                                            f"PRICE_MISMATCH for {product.domain}: "
                                            f"R$ {price} vs Google R$ {google_price} (diff: {price_diff:.1f}%)"
                                        )
                                        raise ValueError(f"PRICE_MISMATCH: {price_diff:.1f}%")

                                screenshot_file = File(
                                    type=FileType.SCREENSHOT,
                                    mime_type="image/png",
                                    storage_path=screenshot_path,
                                    sha256=_calculate_sha256(screenshot_path)
                                )
                                db.add(screenshot_file)
                                db.flush()

                                source = QuoteSource(
                                    quote_request_id=quote_request_id,
                                    url=product.url,
                                    domain=product.domain,
                                    page_title=product.title,
                                    price_value=final_price,
                                    currency="BRL",
                                    extraction_method=final_method,
                                    screenshot_file_id=screenshot_file.id,
                                    is_accepted=True
                                )
                                db.add(source)
                                valid_sources.append(source)
                                valid_sources_by_url[product.url] = source
                                valid_prices[product.url] = float(final_price)

                                logger.info(f"    ✓ Added [{len(valid_sources)}/{num_quotes}]: {product.domain} - R$ {final_price}")
                            else:
                                raise ValueError(f"Invalid price: {price}")

                        except Exception as e:
                            logger.error(f"    ✗ Failed {product.domain}: {str(e)[:100]}")
                            new_failures.append(product.url)

                    # Atualizar falhas
                    failed_urls.update(new_failures)

                    # Verificar resultado
                    if len(valid_sources) >= num_quotes:
                        logger.info(f"Success! Got {len(valid_sources)} quotes after {iteration} iterations")
                        break

                    # Verificar produtos restantes
                    untried_global = [p for p in all_products if p.url not in valid_prices and p.url not in failed_urls]

                    logger.info(
                        f"  End iteration {iteration}: {len(valid_sources)}/{num_quotes} quotes, "
                        f"{len(new_failures)} new failures, {len(untried_global)} untried globally"
                    )

                    if not untried_global:
                        # Não há mais produtos para tentar
                        if has_reserve and len(reserve_sources) > len(valid_sources):
                            # Reserva é melhor - usar ela
                            logger.info(
                                f"  No more products. Reserve ({len(reserve_sources)}) > current ({len(valid_sources)}). Using reserve."
                            )
                            valid_sources = reserve_sources
                            valid_sources_by_url = reserve_sources_by_url
                            valid_prices = reserve_prices

                        logger.info(
                            f"All products tested. Final: {len(valid_sources)}/{num_quotes} quotes, "
                            f"{len(failed_urls)} failed"
                        )
                        break

                    # Há produtos restantes - recalcular bloco na próxima iteração
                    if new_failures:
                        logger.info(f"  {len(new_failures)} failures. Recalculating block...")

        def _calculate_best_block(products, valid_prices, max_variation, num_quotes):
            """
            Calcula o melhor bloco único baseado nos produtos disponíveis.
            Prioriza blocos que:
            1. Contêm todos os produtos já validados
            2. Têm produtos não-testados suficientes para completar N cotações
            3. Têm o menor preço base
            """
            if not products:
                return None

            valid_urls = set(valid_prices.keys())
            best_block = None
            best_score = (-1, -1, float('inf'))  # (contains_all_valid, untried_count, min_price)

            for start_idx, start_product in enumerate(products):
                if not start_product.extracted_price:
                    continue

                min_price = float(start_product.extracted_price)
                max_allowed = min_price * (1 + max_variation)

                # Construir bloco
                block = []
                for product in products[start_idx:]:
                    if product.extracted_price and float(product.extracted_price) <= max_allowed:
                        block.append(product)
                    else:
                        break

                if not block:
                    continue

                # Calcular score do bloco
                block_urls = {p.url for p in block}
                valid_in_block = len(valid_urls & block_urls)
                contains_all_valid = valid_in_block == len(valid_urls) if valid_urls else True
                untried = len([p for p in block if p.url not in valid_prices])

                score = (
                    1 if contains_all_valid else 0,  # Prioridade 1: contém todos validados
                    untried,                          # Prioridade 2: mais produtos não-testados
                    -min_price                        # Prioridade 3: menor preço (negativo para ordenar desc->asc)
                )

                if score > best_score:
                    best_score = score
                    best_block = block

            return best_block

        def _create_variation_blocks_local(products, max_variation, min_size=1):
            """Cria blocos de variação localmente (mantido para compatibilidade)"""
            if not products:
                return []

            blocks = []
            for start_idx, start_product in enumerate(products):
                if not start_product.extracted_price:
                    continue
                min_price = float(start_product.extracted_price)
                max_allowed = min_price * (1 + max_variation)

                block = []
                for product in products[start_idx:]:
                    if product.extracted_price and float(product.extracted_price) <= max_allowed:
                        block.append(product)
                    else:
                        break

                if len(block) >= min_size:
                    blocks.append(block)

            return blocks

        asyncio.run(extract_prices_with_block_recalculation())
        db.commit()

        logger.info(f"Extracted {len(valid_sources)} valid prices")

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

    Returns:
        bool: True se deve usar fallback para Google Shopping, False se concluiu com sucesso
    """
    import asyncio
    from app.services.fipe_client import FipeClient
    from app.services.fipe_pdf_generator import FipePDFGenerator

    try:
        fipe_params = analysis_result.fipe_api

        _update_progress(db, quote_request, "searching_fipe", 50,
                        f"Consultando Tabela FIPE para {analysis_result.marca} {analysis_result.modelo}...")

        # Criar cliente FIPE
        fipe_client = FipeClient()

        # Executar busca na FIPE
        async def search_fipe():
            return await fipe_client.search_vehicle(
                vehicle_type=fipe_params.vehicle_type,
                busca_marca=fipe_params.busca_marca or {},
                busca_modelo=fipe_params.busca_modelo or {},
                year_id_estimado=fipe_params.year_id_estimado,
                codigo_fipe=fipe_params.codigo_fipe,
                ano_modelo=analysis_result.especificacoes.get("essenciais", {}).get("ano_modelo") if hasattr(analysis_result, 'especificacoes') else None
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
        payload = quote_request.claude_payload_json or {}
        payload["fipe_result"] = fipe_data
        quote_request.claude_payload_json = payload
        db.commit()

        if not fipe_result.success:
            # FIPE falhou - tentar fallback para Google Shopping se disponível
            if analysis_result.fallback_google_shopping:
                logger.warning(f"FIPE search failed: {fipe_result.error_message}. Trying Google Shopping fallback...")
                quote_request.error_message = f"FIPE: {fipe_result.error_message}. Tentando Google Shopping..."
                db.commit()
                # Alterar query para usar fallback
                analysis_result.query_principal = analysis_result.fallback_google_shopping.get("query_principal", "")
                # Retornar True para continuar com fluxo normal (Google Shopping)
                return True
            else:
                raise ValueError(f"Consulta FIPE falhou: {fipe_result.error_message}")

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

        _update_progress(db, quote_request, "generating_pdf", 85, "Gerando PDF da cotação FIPE...")

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
                analysis_result=analysis_result
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
