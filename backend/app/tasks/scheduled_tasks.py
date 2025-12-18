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
