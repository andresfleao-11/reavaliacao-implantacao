"""
Tasks agendadas (Celery Beat)
- Atualização diária da taxa de câmbio USD -> BRL às 23:00
- Sincronização periódica de dados mestres de inventário
"""
import logging
from datetime import datetime
import asyncio

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Setting
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)


# ===== Inventory Sync Tasks =====

@celery_app.task(name="sync_inventory_master_data")
def sync_inventory_master_data():
    """
    Task para sincronizar dados mestres de inventário dos sistemas externos.
    Executada diariamente às 02:00 (horário de baixo uso).

    Sincroniza:
    - UGs (Unidades Gestoras)
    - ULs (Unidades Locais)
    - Situações Físicas
    - Características
    """
    from app.models import ExternalSystem
    from app.services.external_system_sync import ExternalSystemSyncService

    logger.info("Iniciando sincronização automática de dados mestres de inventário...")

    db = SessionLocal()
    results = {}
    errors = []

    try:
        # Buscar todos os sistemas externos ativos
        systems = db.query(ExternalSystem).filter(
            ExternalSystem.is_active == True
        ).all()

        if not systems:
            logger.warning("Nenhum sistema externo ativo encontrado para sincronização")
            return {"success": True, "message": "Nenhum sistema configurado", "results": {}}

        for system in systems:
            logger.info(f"Sincronizando dados do sistema: {system.name}")
            system_results = {}

            try:
                sync_service = ExternalSystemSyncService(db, system)

                # Executar sync_all de forma síncrona
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    sync_result = loop.run_until_complete(sync_service.sync_all())
                    system_results = sync_result
                finally:
                    loop.close()

                results[system.name] = {
                    "success": True,
                    "data": system_results
                }

                logger.info(f"Sincronização do sistema {system.name} concluída: {system_results}")

            except Exception as e:
                error_msg = f"Erro ao sincronizar sistema {system.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                results[system.name] = {
                    "success": False,
                    "error": str(e)
                }

        return {
            "success": len(errors) == 0,
            "results": results,
            "errors": errors if errors else None,
            "synced_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Erro na sincronização automática: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="sync_inventory_master_data_for_system")
def sync_inventory_master_data_for_system(system_id: int):
    """
    Task para sincronizar dados mestres de um sistema externo específico.
    Pode ser chamada manualmente via API.
    """
    from app.models import ExternalSystem
    from app.services.external_system_sync import ExternalSystemSyncService

    logger.info(f"Iniciando sincronização do sistema {system_id}...")

    db = SessionLocal()

    try:
        system = db.query(ExternalSystem).filter(ExternalSystem.id == system_id).first()

        if not system:
            return {"success": False, "error": "Sistema não encontrado"}

        if not system.is_active:
            return {"success": False, "error": "Sistema está desativado"}

        sync_service = ExternalSystemSyncService(db, system)

        # Executar sync_all de forma síncrona
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(sync_service.sync_all())
        finally:
            loop.close()

        logger.info(f"Sincronização do sistema {system.name} concluída: {results}")

        return {
            "success": True,
            "system_name": system.name,
            "results": results,
            "synced_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Erro na sincronização do sistema {system_id}: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="check_inventory_sessions_status")
def check_inventory_sessions_status():
    """
    Task para verificar e atualizar status de sessões de inventário.
    Executada a cada hora.

    - Identifica sessões em andamento há muito tempo
    - Verifica sessões com leituras pendentes de sincronização
    - Atualiza estatísticas de sessões
    """
    from app.models import InventorySession, InventorySessionStatus
    from app.models.inventory_session import InventoryReadAsset, InventoryExpectedAsset
    from datetime import timedelta
    from sqlalchemy import func

    logger.info("Verificando status de sessões de inventário...")

    db = SessionLocal()
    updated = 0
    warnings = []

    try:
        # Buscar sessões em andamento há mais de 7 dias
        cutoff = datetime.utcnow() - timedelta(days=7)
        old_sessions = db.query(InventorySession).filter(
            InventorySession.status == InventorySessionStatus.IN_PROGRESS.value,
            InventorySession.started_at < cutoff
        ).all()

        for session in old_sessions:
            warning = f"Sessão {session.code} em andamento há mais de 7 dias (iniciada em {session.started_at})"
            logger.warning(warning)
            warnings.append(warning)

        # Atualizar estatísticas de todas as sessões ativas
        active_sessions = db.query(InventorySession).filter(
            InventorySession.status.in_([
                InventorySessionStatus.IN_PROGRESS.value,
                InventorySessionStatus.PAUSED.value
            ])
        ).all()

        for session in active_sessions:
            # Contar bens por categoria
            found_count = db.query(func.count(InventoryReadAsset.id)).filter(
                InventoryReadAsset.session_id == session.id,
                InventoryReadAsset.category == 'found'
            ).scalar() or 0

            unregistered_count = db.query(func.count(InventoryReadAsset.id)).filter(
                InventoryReadAsset.session_id == session.id,
                InventoryReadAsset.category == 'unregistered'
            ).scalar() or 0

            written_off_count = db.query(func.count(InventoryReadAsset.id)).filter(
                InventoryReadAsset.session_id == session.id,
                InventoryReadAsset.category == 'written_off'
            ).scalar() or 0

            expected_count = db.query(func.count(InventoryExpectedAsset.id)).filter(
                InventoryExpectedAsset.session_id == session.id
            ).scalar() or 0

            not_found_count = expected_count - found_count

            # Atualizar estatísticas se mudaram
            if (session.total_expected != expected_count or
                session.total_found != found_count or
                session.total_not_found != not_found_count or
                session.total_unregistered != unregistered_count or
                session.total_written_off != written_off_count):

                session.total_expected = expected_count
                session.total_found = found_count
                session.total_not_found = max(0, not_found_count)
                session.total_unregistered = unregistered_count
                session.total_written_off = written_off_count
                updated += 1

        db.commit()

        logger.info(f"Verificação de sessões concluída: {updated} atualizadas, {len(warnings)} avisos")

        return {
            "success": True,
            "sessions_updated": updated,
            "warnings": warnings if warnings else None
        }

    except Exception as e:
        logger.error(f"Erro ao verificar sessões: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="update_exchange_rate")
def update_exchange_rate():
    """
    Task para atualizar a taxa de câmbio USD -> BRL do Banco Central.
    Executada diariamente às 23:00 (horário de Brasília).
    """
    from app.services.bcb_client import fetch_exchange_rate_sync

    logger.info("Iniciando atualização da taxa de câmbio BCB...")

    db = SessionLocal()
    try:
        # Buscar cotação do BCB
        result = fetch_exchange_rate_sync()

        if not result or not result.get("rate"):
            logger.error("Não foi possível obter a cotação do BCB")
            return {"success": False, "error": "Falha ao obter cotação do BCB"}

        rate = result["rate"]
        bcb_date = result.get("date", "")

        logger.info(f"Cotação obtida: USD 1 = BRL {rate} (data BCB: {bcb_date})")

        # Atualizar no banco de dados
        setting = db.query(Setting).filter(Setting.key == "cost_config").first()

        if not setting:
            setting = Setting(key="cost_config", value_json={})
            db.add(setting)

        current = dict(setting.value_json) if setting.value_json else {}

        current["usd_to_brl_rate"] = rate
        current["exchange_updated_at"] = datetime.now().isoformat()
        current["exchange_source"] = "BCB_PTAX"
        current["exchange_bcb_date"] = bcb_date

        setting.value_json = current
        flag_modified(setting, "value_json")
        db.commit()

        logger.info(f"Taxa de câmbio atualizada com sucesso: {rate}")

        return {
            "success": True,
            "rate": rate,
            "bcb_date": bcb_date,
            "updated_at": current["exchange_updated_at"]
        }

    except Exception as e:
        logger.error(f"Erro ao atualizar taxa de câmbio: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="manual_update_exchange_rate")
def manual_update_exchange_rate():
    """
    Task para atualização manual da taxa de câmbio.
    Pode ser chamada via API.
    """
    return update_exchange_rate()


@celery_app.task(name="recover_stuck_quotes")
def recover_stuck_quotes():
    """
    Task para recuperar cotacoes travadas.
    Executada a cada 5 minutos.

    Identifica cotacoes com status PROCESSING mas sem heartbeat recente
    e as coloca novamente na fila de processamento.
    """
    from app.services.checkpoint_manager import (
        find_stuck_quotes,
        reset_stuck_quote,
        get_processing_stats,
        HEARTBEAT_TIMEOUT_MINUTES
    )
    from app.tasks.quote_tasks import process_quote_request

    logger.info("Iniciando verificacao de cotacoes travadas...")

    db = SessionLocal()
    recovered = 0
    errors = 0

    try:
        # Buscar cotacoes travadas
        stuck_quotes = find_stuck_quotes(db, timeout_minutes=HEARTBEAT_TIMEOUT_MINUTES)

        if not stuck_quotes:
            logger.info("Nenhuma cotacao travada encontrada")
            return {"success": True, "recovered": 0}

        logger.warning(f"Encontradas {len(stuck_quotes)} cotacoes travadas")

        for quote in stuck_quotes:
            try:
                # Log detalhado
                logger.info(
                    f"Cotacao {quote.id} travada: "
                    f"checkpoint={quote.processing_checkpoint}, "
                    f"last_heartbeat={quote.last_heartbeat}, "
                    f"worker={quote.worker_id}"
                )

                # Reseta a cotacao
                reset_stuck_quote(db, quote)

                # Re-enfileira para processamento
                process_quote_request.delay(quote.id)
                recovered += 1

                logger.info(f"Cotacao {quote.id} re-enfileirada para processamento")

            except Exception as e:
                logger.error(f"Erro ao recuperar cotacao {quote.id}: {str(e)}")
                errors += 1

        # Log de estatisticas
        stats = get_processing_stats(db)
        logger.info(f"Estatisticas apos recuperacao: {stats}")

        return {
            "success": True,
            "recovered": recovered,
            "errors": errors,
            "total_stuck": len(stuck_quotes)
        }

    except Exception as e:
        logger.error(f"Erro na task de recuperacao: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="cleanup_old_processing")
def cleanup_old_processing():
    """
    Task para limpar cotacoes muito antigas em PROCESSING.
    Executada diariamente.

    Cotacoes em PROCESSING por mais de 24 horas sao marcadas como ERROR.
    """
    from datetime import timedelta
    from app.models.quote_request import QuoteRequest, QuoteStatus
    from sqlalchemy import and_

    logger.info("Iniciando limpeza de cotacoes antigas em PROCESSING...")

    db = SessionLocal()
    cleaned = 0

    try:
        # Cotacoes em PROCESSING por mais de 24 horas
        cutoff = datetime.utcnow() - timedelta(hours=24)

        old_processing = db.query(QuoteRequest).filter(
            and_(
                QuoteRequest.status == QuoteStatus.PROCESSING,
                QuoteRequest.created_at < cutoff
            )
        ).all()

        for quote in old_processing:
            logger.warning(
                f"Cotacao {quote.id} em PROCESSING por mais de 24h. "
                f"Criada em {quote.created_at}. Marcando como ERROR."
            )

            quote.status = QuoteStatus.ERROR
            quote.error_message = "Timeout: processamento excedeu 24 horas"
            quote.completed_at = datetime.utcnow()
            quote.worker_id = None
            cleaned += 1

        db.commit()

        logger.info(f"Limpeza concluida: {cleaned} cotacoes marcadas como ERROR")

        return {"success": True, "cleaned": cleaned}

    except Exception as e:
        logger.error(f"Erro na limpeza: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="fix_stuck_batches")
def fix_stuck_batches():
    """
    Task para corrigir lotes com status incorreto.
    Executada a cada 10 minutos.

    Verifica lotes em PROCESSING onde todas as cotacoes ja terminaram
    e atualiza o status corretamente.
    """
    from app.models.batch_quote import BatchQuoteJob, BatchJobStatus
    from app.models.quote_request import QuoteRequest, QuoteStatus
    from sqlalchemy import func

    logger.info("Verificando lotes com status incorreto...")

    db = SessionLocal()
    fixed = 0

    try:
        # Buscar lotes em PROCESSING
        processing_batches = db.query(BatchQuoteJob).filter(
            BatchQuoteJob.status == BatchJobStatus.PROCESSING
        ).all()

        for batch in processing_batches:
            # Contar cotacoes por status
            status_counts = db.query(
                QuoteRequest.status,
                func.count(QuoteRequest.id)
            ).filter(
                QuoteRequest.batch_job_id == batch.id
            ).group_by(QuoteRequest.status).all()

            completed = 0
            failed = 0
            cancelled = 0
            processing = 0

            for status, count in status_counts:
                if status in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW]:
                    completed += count
                elif status == QuoteStatus.ERROR:
                    failed += count
                elif status == QuoteStatus.CANCELLED:
                    cancelled += count
                elif status == QuoteStatus.PROCESSING:
                    processing += count

            # Atualizar contadores
            batch.completed_items = completed
            batch.failed_items = failed

            # Se nao ha cotacoes em PROCESSING, o lote terminou
            if processing == 0:
                total_finished = completed + failed + cancelled

                if total_finished >= batch.total_items:
                    if failed > 0 and completed > 0:
                        batch.status = BatchJobStatus.PARTIALLY_COMPLETED
                        batch.error_message = f"{failed} de {batch.total_items} cotacoes falharam"
                    elif completed == 0:
                        batch.status = BatchJobStatus.ERROR
                        batch.error_message = f"Todas as {batch.total_items} cotacoes falharam"
                    else:
                        batch.status = BatchJobStatus.COMPLETED

                    logger.info(
                        f"Lote {batch.id} corrigido: status={batch.status.value}, "
                        f"completed={completed}, failed={failed}"
                    )
                    fixed += 1

                    # Gerar arquivos de resultado
                    try:
                        from app.services.batch_result_generator import generate_batch_results
                        generate_batch_results(db, batch.id)
                    except Exception as e:
                        logger.error(f"Erro ao gerar resultados do lote {batch.id}: {e}")

        db.commit()

        logger.info(f"Verificacao de lotes concluida: {fixed} lotes corrigidos")

        return {"success": True, "fixed": fixed}

    except Exception as e:
        logger.error(f"Erro ao verificar lotes: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
