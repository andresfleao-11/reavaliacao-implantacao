"""
Tasks agendadas (Celery Beat)
- Atualização diária da taxa de câmbio USD -> BRL às 23:00
"""
import logging
from datetime import datetime

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import Setting
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)


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
