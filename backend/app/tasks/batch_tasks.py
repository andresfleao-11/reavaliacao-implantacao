"""
Tasks Celery para processamento de cotacao em lote.
Implementa processamento paralelo com capacidade de retomada.
"""
from celery import Task, group, chord
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import QuoteRequest, QuoteSource, File, IntegrationLog, BlockedDomain
from app.models.quote_request import QuoteStatus, QuoteInputType
from app.models.batch_quote import BatchQuoteJob, BatchJobStatus
from app.models.file import FileType
from app.models.financial import ApiCostConfig, FinancialTransaction
from app.services.claude_client import ClaudeClient
from app.services.openai_client import OpenAIClient
from app.services.search_provider import SerpApiProvider
from app.services.price_extractor import PriceExtractor
from app.services.integration_logger import log_anthropic_call, log_serpapi_call
from app.tasks.quote_tasks import _process_fipe_quote, _update_progress
from app.core.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from decimal import Decimal
import os
import hashlib
from datetime import datetime, timezone
import logging
import asyncio

logger = logging.getLogger(__name__)


class BatchTask(Task):
    """Classe base para tasks de lote com tratamento de erros."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        batch_job_id = args[0] if args else None
        if batch_job_id:
            db = SessionLocal()
            try:
                batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_job_id).first()
                if batch and batch.status != BatchJobStatus.CANCELLED:
                    batch.status = BatchJobStatus.ERROR
                    batch.error_message = str(exc)[:1000]
                    db.commit()
            finally:
                db.close()


def _update_batch_progress(db: Session, batch: BatchQuoteJob):
    """Atualiza contadores de progresso do lote."""
    # Contar cotacoes por status
    completed = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch.id,
        QuoteRequest.status.in_([QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW])
    ).count()

    failed = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch.id,
        QuoteRequest.status.in_([QuoteStatus.ERROR, QuoteStatus.CANCELLED])
    ).count()

    batch.completed_items = completed
    batch.failed_items = failed
    db.commit()
    db.refresh(batch)


def _get_integration_setting(db: Session, provider: str, key: str) -> Optional[str]:
    """Busca configuracao de integracao."""
    from app.models import IntegrationSetting
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


def _get_integration_other_setting(db: Session, provider: str, setting_name: str) -> Optional[str]:
    """Busca configuracao extra de integracao."""
    from app.models import IntegrationSetting
    integration = db.query(IntegrationSetting).filter(
        IntegrationSetting.provider == provider
    ).first()
    if integration and integration.settings_json:
        return integration.settings_json.get(setting_name)
    return None


def _get_blocked_domains(db: Session) -> set:
    """Carrega os domínios bloqueados do banco de dados"""
    blocked = db.query(BlockedDomain.domain).all()
    return {d.domain for d in blocked}


def _get_parameter(db: Session, param_name: str, default, config_version_id: int = None):
    """Busca parametro de configuracao (prioridade: projeto > global > default)."""
    from app.models import Setting
    from app.models.project_config import ProjectConfigVersion

    # Primeiro tenta config do projeto
    if config_version_id:
        config = db.query(ProjectConfigVersion).filter(
            ProjectConfigVersion.id == config_version_id
        ).first()
        if config:
            value = getattr(config, param_name, None)
            if value is not None:
                return value

    # Depois tenta setting global
    setting = db.query(Setting).filter(Setting.key == param_name).first()
    if setting:
        try:
            if isinstance(default, int):
                return int(setting.value)
            elif isinstance(default, float):
                return float(setting.value)
            return setting.value
        except (ValueError, TypeError):
            return default

    return default


def _register_ai_cost(db: Session, quote_request: QuoteRequest, model: str, total_tokens: int, provider: str = "anthropic"):
    """Registra o custo da chamada de IA."""
    cost_config = db.query(ApiCostConfig).filter(
        ApiCostConfig.api_name == provider.upper()
    ).first()

    if cost_config:
        # Calcular custo em USD
        cost_per_1k_input = 0.003  # Default fallback
        cost_per_1k_output = 0.015

        # Estimar input/output tokens (50/50 split)
        input_tokens = total_tokens // 2
        output_tokens = total_tokens - input_tokens

        cost_usd = (input_tokens / 1000) * cost_per_1k_input + (output_tokens / 1000) * cost_per_1k_output
        cost_brl = cost_usd * float(cost_config.cost_per_token_brl) if cost_config.cost_per_token_brl else cost_usd * 5.0

        transaction = FinancialTransaction(
            quote_id=quote_request.id,
            api_cost_config_id=cost_config.id,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            tokens_total=total_tokens,
            calculated_cost_brl=Decimal(str(cost_brl))
        )
        db.add(transaction)
        db.commit()


@celery_app.task(base=BatchTask, bind=True)
def process_batch_job(self, batch_job_id: int, resume: bool = False):
    """
    Task coordenadora para processamento de lote.

    Dispara tasks individuais para cada cotacao do lote.
    As tasks individuais atualizam o progresso do batch quando completam.
    """
    db = SessionLocal()

    try:
        batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_job_id).first()
        if not batch:
            raise ValueError(f"BatchQuoteJob {batch_job_id} not found")

        logger.info(f"Processing batch job {batch_job_id} (resume={resume})")

        # Atualizar status para PROCESSING
        batch.status = BatchJobStatus.PROCESSING
        db.commit()

        # Buscar cotacoes pendentes
        if resume:
            # Apenas cotacoes com status PROCESSING (resetadas pelo resume)
            pending_quotes = db.query(QuoteRequest).filter(
                QuoteRequest.batch_job_id == batch_job_id,
                QuoteRequest.status == QuoteStatus.PROCESSING
            ).order_by(QuoteRequest.batch_index).all()
        else:
            # Todas as cotacoes do lote
            pending_quotes = db.query(QuoteRequest).filter(
                QuoteRequest.batch_job_id == batch_job_id
            ).order_by(QuoteRequest.batch_index).all()

        if not pending_quotes:
            logger.info(f"No pending quotes for batch {batch_job_id}")
            batch.status = BatchJobStatus.COMPLETED
            db.commit()
            return

        logger.info(f"Found {len(pending_quotes)} quotes to process")

        # Dispara todas as tasks de uma vez
        # Cada task atualiza o batch ao completar
        quote_ids = [q.id for q in pending_quotes]

        for qid in quote_ids:
            process_batch_quote.delay(qid, batch_job_id)

        logger.info(f"Dispatched {len(quote_ids)} quote tasks for batch {batch_job_id}")

    except Exception as e:
        logger.error(f"Error processing batch {batch_job_id}: {e}")
        batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_job_id).first()
        if batch and batch.status != BatchJobStatus.CANCELLED:
            batch.status = BatchJobStatus.ERROR
            batch.error_message = str(e)[:1000]
            db.commit()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_batch_quote(self, quote_request_id: int, batch_job_id: int):
    """
    Processa uma cotacao individual do lote.

    Implementa checkpoint salvando resposta do Google Shopping
    para permitir retomada em caso de interrupcao.
    """
    db = SessionLocal()

    try:
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if not quote_request:
            raise ValueError(f"QuoteRequest {quote_request_id} not found")

        # Verificar se ja foi processada
        if quote_request.status in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW, QuoteStatus.CANCELLED]:
            logger.info(f"Quote {quote_request_id} already processed with status {quote_request.status}")
            return {"status": "skipped", "quote_id": quote_request_id}

        logger.info(f"Processing batch quote {quote_request_id} (batch {batch_job_id})")

        # Atualizar progresso
        quote_request.current_step = "initializing"
        quote_request.progress_percentage = 5
        quote_request.step_details = "Carregando configuracoes..."
        db.commit()

        # Determinar provedor de IA
        ai_provider = _get_integration_other_setting(db, "ANTHROPIC", "ai_provider")
        if not ai_provider:
            ai_provider = _get_integration_other_setting(db, "OPENAI", "ai_provider")
        if not ai_provider:
            ai_provider = settings.AI_PROVIDER

        # Configurar cliente de IA
        if ai_provider == "openai":
            api_key = _get_integration_setting(db, "OPENAI", "api_key") or settings.OPENAI_API_KEY
            model = _get_integration_other_setting(db, "OPENAI", "model") or settings.OPENAI_MODEL
            ai_client = OpenAIClient(api_key=api_key, model=model)
            integration_type = "openai"
        else:
            api_key = _get_integration_setting(db, "ANTHROPIC", "api_key") or settings.ANTHROPIC_API_KEY
            model = _get_integration_other_setting(db, "ANTHROPIC", "model") or settings.ANTHROPIC_MODEL
            ai_client = ClaudeClient(api_key=api_key, model=model)
            integration_type = "anthropic"

        # Carregar imagens se houver
        input_images = db.query(File).filter(
            File.quote_request_id == quote_request_id,
            File.type == FileType.INPUT_IMAGE
        ).all()

        image_data_list = []
        for img_file in input_images:
            try:
                with open(img_file.storage_path, 'rb') as f:
                    image_data_list.append(f.read())
            except Exception as e:
                logger.error(f"Error reading image {img_file.storage_path}: {e}")

        # Analise de IA
        quote_request.current_step = "analyzing"
        quote_request.progress_percentage = 15
        quote_request.step_details = "Analisando produto com IA..."
        db.commit()

        analysis_result = asyncio.run(
            ai_client.analyze_item(
                input_text=quote_request.input_text,
                image_files=image_data_list if image_data_list else None
            )
        )

        quote_request.claude_payload_json = analysis_result.dict()
        quote_request.search_query_final = analysis_result.query_principal
        db.commit()

        # Registrar logs de IA
        for call_log in analysis_result.call_logs:
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
                activity=f"[Batch] {call_log.activity if hasattr(call_log, 'activity') else call_log.get('activity', '')}",
                integration_type=integration_type,
                request_data={"prompt": prompt_text} if prompt_text else None
            )

        # Registrar custo de IA
        if analysis_result.total_tokens_used > 0:
            _register_ai_cost(db, quote_request, model, analysis_result.total_tokens_used, ai_provider)

        # Verificar se é veículo (processamento via FIPE)
        if analysis_result.tipo_processamento == "FIPE" and analysis_result.fipe_api:
            logger.info(f"[Batch] Detected vehicle - using FIPE API flow for quote {quote_request_id}")
            use_fallback = _process_fipe_quote(db, quote_request, analysis_result)
            if not use_fallback:
                # FIPE processou com sucesso - o status já foi atualizado em _process_fipe_quote
                # Mas precisamos garantir que o batch seja atualizado
                db.refresh(quote_request)
                logger.info(f"[Batch] FIPE quote {quote_request_id} completed successfully")
                # Atualizar progresso do batch ANTES de retornar
                _update_batch_on_quote_complete(db, batch_job_id)
                return {"status": "completed", "quote_id": quote_request_id, "source": "FIPE"}
            # FIPE falhou, continuar com Google Shopping usando query de fallback
            logger.info(f"[Batch] FIPE failed, falling back to Google Shopping with query: {analysis_result.query_principal}")

        # Verificar query valida (para fluxo Google Shopping)
        if not analysis_result.query_principal or not analysis_result.query_principal.strip():
            raise ValueError("IA nao conseguiu gerar query de busca valida")

        # Configurar SerpAPI
        serpapi_key = _get_integration_setting(db, "SERPAPI", "api_key") or settings.SERPAPI_API_KEY
        config_version_id = quote_request.config_version_id
        serpapi_location = _get_parameter(db, "serpapi_location", "Brazil", config_version_id)
        blocked_domains = _get_blocked_domains(db)

        search_provider = SerpApiProvider(
            api_key=serpapi_key,
            engine=settings.SERPAPI_ENGINE,
            location=serpapi_location,
            blocked_domains=blocked_domains
        )

        num_quotes = int(_get_parameter(db, "numero_cotacoes_por_pesquisa", 3, config_version_id))
        variacao_maxima = float(_get_parameter(db, "variacao_maxima_percent", 25, config_version_id)) / 100

        # CHECKPOINT: Verificar se ja temos resposta do Google Shopping salva
        if quote_request.google_shopping_response_json:
            logger.info(f"Resuming quote {quote_request_id} from cached Shopping response")
            # TODO: Implementar parse do cache e continuar de onde parou
            # Por enquanto, refaz a busca
            quote_request.google_shopping_response_json = None
            db.commit()

        # Buscar produtos
        quote_request.current_step = "searching"
        quote_request.progress_percentage = 40
        quote_request.step_details = f"Buscando '{analysis_result.query_principal}'..."
        db.commit()

        search_results, search_log = asyncio.run(
            search_provider.search_products(
                query=analysis_result.query_principal,
                limit=num_quotes,
                variacao_maxima=variacao_maxima
            )
        )

        # CHECKPOINT: Salvar resposta do Google Shopping
        quote_request.google_shopping_response_json = {
            "results_count": len(search_results),
            "search_log": search_log.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        quote_request.shopping_response_saved_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"Quote {quote_request_id}: Found {len(search_results)} results")

        # Salvar log de busca
        search_log_entry = IntegrationLog(
            quote_request_id=quote_request.id,
            integration_type="search_log",
            activity="[Batch] Log detalhado da busca",
            response_summary=search_log.model_dump()
        )
        db.add(search_log_entry)
        db.commit()

        # Registrar chamadas SerpAPI
        for api_call in search_provider.api_calls_made:
            log_serpapi_call(
                db=db,
                quote_request_id=quote_request.id,
                api_used=api_call["api_used"],
                search_url=api_call["search_url"],
                activity=f"[Batch] {api_call['activity']}",
                request_data={"query": analysis_result.query_principal, "limit": num_quotes},
                response_summary={"results_found": len(search_results)} if api_call["api_used"] == "google_shopping" else None,
                product_link=api_call.get("product_link")
            )

        # Processar resultados com captura de screenshots
        quote_request.current_step = "extracting"
        quote_request.progress_percentage = 60
        quote_request.step_details = "Extraindo precos e capturando screenshots..."
        db.commit()

        # Salvar fontes de preco com screenshots
        valid_sources = []

        async def process_sources():
            sources = []
            source_index = 0

            async with PriceExtractor() as extractor:
                for result in search_results:
                    if len(sources) >= num_quotes:
                        break

                    if not result.url or not result.extracted_price or result.extracted_price <= 0:
                        continue

                    # Tentar extrair preco com screenshot
                    try:
                        screenshot_filename = f"screenshot_{quote_request.id}_{source_index}.png"
                        screenshot_path = os.path.join(settings.STORAGE_PATH, "screenshots", screenshot_filename)
                        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

                        price, method = await extractor.extract_price_and_screenshot(
                            result.url,
                            screenshot_path
                        )

                        if price and price > Decimal("1"):
                            final_price = price
                            google_price = result.extracted_price

                            # Validar preco contra o Google
                            if google_price and google_price > Decimal("0"):
                                price_diff_percent = abs(float(price) - float(google_price)) / float(google_price) * 100
                                if price_diff_percent > 15:
                                    logger.warning(
                                        f"Price mismatch for {result.domain}: "
                                        f"R$ {price} vs Google R$ {google_price} (diff: {price_diff_percent:.1f}%). Using Google."
                                    )
                                    final_price = google_price
                                    method = "LLM"

                            # Criar arquivo de screenshot
                            screenshot_file = File(
                                type=FileType.SCREENSHOT,
                                mime_type="image/png",
                                storage_path=screenshot_path,
                                sha256=_calculate_sha256(screenshot_path)
                            )
                            db.add(screenshot_file)
                            db.flush()

                            source = QuoteSource(
                                quote_request_id=quote_request.id,
                                url=result.url,
                                domain=result.domain or result.store_name or "",
                                page_title=result.title or "",
                                price_value=Decimal(str(final_price)),
                                currency="BRL",
                                extraction_method=method or "LLM",
                                screenshot_file_id=screenshot_file.id,
                                captured_at=datetime.now(timezone.utc),
                                is_outlier=False,
                                is_accepted=True
                            )
                            db.add(source)
                            sources.append(source)
                            source_index += 1
                            logger.info(f"✓ Added [{len(sources)}/{num_quotes}]: {result.domain} - R$ {final_price}")
                            continue

                    except Exception as e:
                        logger.error(f"✗ Failed extraction from {result.domain}: {str(e)[:100]}")
                        # Não adicionar com fallback - continuar tentando outros produtos

            logger.info(f"Extraction complete: {len(sources)}/{num_quotes} quotes obtained")
            return sources

        valid_sources = asyncio.run(process_sources())
        db.commit()

        # Calcular estatisticas
        if valid_sources:
            prices = [float(s.price_value) for s in valid_sources]
            quote_request.valor_medio = Decimal(str(sum(prices) / len(prices)))
            quote_request.valor_minimo = Decimal(str(min(prices)))
            quote_request.valor_maximo = Decimal(str(max(prices)))

            if quote_request.valor_minimo > 0:
                variacao = (float(quote_request.valor_maximo) / float(quote_request.valor_minimo) - 1) * 100
                quote_request.variacao_percentual = Decimal(str(variacao))

        # Determinar status final
        if len(valid_sources) >= num_quotes:
            quote_request.status = QuoteStatus.DONE
        elif len(valid_sources) > 0:
            quote_request.status = QuoteStatus.AWAITING_REVIEW
            quote_request.error_message = f"Apenas {len(valid_sources)} de {num_quotes} fontes encontradas"
        else:
            quote_request.status = QuoteStatus.ERROR
            quote_request.error_message = "Nenhuma fonte de preco encontrada"

        quote_request.current_step = "completed"
        quote_request.progress_percentage = 100
        quote_request.step_details = f"Cotacao finalizada com {len(valid_sources)} fontes"
        db.commit()

        logger.info(f"Quote {quote_request_id} completed with status {quote_request.status.value}")

        # Atualizar progresso do batch e verificar se todos concluiram
        _update_batch_on_quote_complete(db, batch_job_id)

        return {"status": "success", "quote_id": quote_request_id, "sources": len(valid_sources)}

    except Exception as e:
        logger.error(f"Error processing batch quote {quote_request_id}: {e}")

        # Atualizar status de erro
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if quote_request and quote_request.status not in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW, QuoteStatus.CANCELLED]:
            quote_request.status = QuoteStatus.ERROR
            quote_request.error_message = str(e)[:1000]
            quote_request.current_step = "error"
            quote_request.step_details = f"Erro: {str(e)[:500]}"
            db.commit()

        # Atualizar progresso do batch
        _update_batch_on_quote_complete(db, batch_job_id)

        # Retry se for erro temporario
        if "rate_limit" in str(e).lower() or "429" in str(e):
            try:
                self.retry(exc=e)
            except Exception:
                pass

        raise

    finally:
        db.close()


def _update_batch_on_quote_complete(db: Session, batch_job_id: int):
    """Atualiza o batch apos uma cotacao completar e verifica se todas terminaram."""
    try:
        batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_job_id).first()
        if not batch:
            return

        # Contar cotacoes por status
        completed = db.query(QuoteRequest).filter(
            QuoteRequest.batch_job_id == batch_job_id,
            QuoteRequest.status.in_([QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW])
        ).count()

        failed = db.query(QuoteRequest).filter(
            QuoteRequest.batch_job_id == batch_job_id,
            QuoteRequest.status == QuoteStatus.ERROR
        ).count()

        batch.completed_items = completed
        batch.failed_items = failed

        # Verificar se todas as cotacoes terminaram
        total_finished = completed + failed
        if total_finished >= batch.total_items:
            if failed > 0:
                batch.status = BatchJobStatus.PARTIALLY_COMPLETED
                batch.error_message = f"{failed} de {batch.total_items} cotacoes falharam"
            else:
                batch.status = BatchJobStatus.COMPLETED

            logger.info(f"Batch {batch_job_id} finished: {completed} success, {failed} failed")

        db.commit()
    except Exception as e:
        logger.error(f"Error updating batch {batch_job_id}: {e}")
        db.rollback()


def _calculate_sha256(file_path: str) -> str:
    """Calcula o hash SHA256 de um arquivo."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
