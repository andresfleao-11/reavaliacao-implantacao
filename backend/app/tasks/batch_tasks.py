"""
Tasks Celery para processamento de cotacao em lote.
Implementa processamento paralelo com capacidade de retomada.

Nota: A lógica de processamento individual foi delegada para quote_tasks.py
para garantir consistência entre cotações individuais e em lote.
"""
from celery import Task
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import QuoteRequest, QuoteSource
from app.models.quote_request import QuoteStatus
from app.models.batch_quote import BatchQuoteJob, BatchJobStatus
from sqlalchemy.orm import Session
import logging

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

    Delega todo o processamento para process_quote_request (quote_tasks.py)
    para garantir que lote e individual usem a mesma lógica.
    """
    from app.tasks.quote_tasks import process_quote_request as process_quote_task

    db = SessionLocal()

    try:
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if not quote_request:
            raise ValueError(f"QuoteRequest {quote_request_id} not found")

        # Verificar se ja foi processada
        if quote_request.status in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW, QuoteStatus.CANCELLED]:
            logger.info(f"Quote {quote_request_id} already processed with status {quote_request.status}")
            _update_batch_on_quote_complete(db, batch_job_id)
            return {"status": "skipped", "quote_id": quote_request_id}

        logger.info(f"[Batch] Processing quote {quote_request_id} (batch {batch_job_id}) - delegating to process_quote_request")

        # Fechar conexão antes de delegar (a task principal vai abrir sua própria conexão)
        db.close()
        db = None

        # Delegar processamento para a task principal (execução síncrona dentro desta task)
        # Usar apply() ao invés de delay() para execução síncrona
        result = process_quote_task.apply(args=[quote_request_id])

        # Reconectar e atualizar batch
        db = SessionLocal()

        # Verificar resultado
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        num_sources = db.query(QuoteSource).filter(QuoteSource.quote_request_id == quote_request_id).count()

        logger.info(f"[Batch] Quote {quote_request_id} completed with status {quote_request.status.value}, {num_sources} sources")

        # Atualizar progresso do batch e verificar se todos concluiram
        _update_batch_on_quote_complete(db, batch_job_id)

        return {"status": "success", "quote_id": quote_request_id, "sources": num_sources}

    except Exception as e:
        logger.error(f"Error processing batch quote {quote_request_id}: {e}")

        if db is None:
            db = SessionLocal()

        # Atualizar status de erro (se ainda não foi atualizado pela task principal)
        quote_request = db.query(QuoteRequest).filter(QuoteRequest.id == quote_request_id).first()
        if quote_request and quote_request.status not in [QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW, QuoteStatus.CANCELLED, QuoteStatus.ERROR]:
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
        if db:
            db.close()


def _update_batch_on_quote_complete(db: Session, batch_job_id: int):
    """
    Atualiza o batch apos uma cotacao completar e verifica se todas terminaram.

    IMPORTANTE: Esta função é chamada de forma concorrente por múltiplas tasks.
    Usa FOR UPDATE para evitar race conditions na atualização.
    """
    from sqlalchemy import func

    try:
        # Lock no batch para evitar race condition
        batch = db.query(BatchQuoteJob).filter(
            BatchQuoteJob.id == batch_job_id
        ).with_for_update().first()

        if not batch:
            return

        # Contar cotacoes por status (inclui CANCELLED)
        status_counts = db.query(
            QuoteRequest.status,
            func.count(QuoteRequest.id)
        ).filter(
            QuoteRequest.batch_job_id == batch_job_id
        ).group_by(QuoteRequest.status).all()

        # Processar contagens
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

        batch.completed_items = completed
        batch.failed_items = failed

        # Total de finalizados (exclui PROCESSING)
        total_finished = completed + failed + cancelled

        logger.info(
            f"Batch {batch_job_id} progress: "
            f"completed={completed}, failed={failed}, cancelled={cancelled}, "
            f"processing={processing}, total={batch.total_items}"
        )

        # Verificar se todas as cotacoes terminaram (nenhuma em PROCESSING)
        if processing == 0 and total_finished >= batch.total_items:
            if failed > 0 and completed > 0:
                batch.status = BatchJobStatus.PARTIALLY_COMPLETED
                batch.error_message = f"{failed} de {batch.total_items} cotacoes falharam"
            elif completed == 0:
                batch.status = BatchJobStatus.ERROR
                batch.error_message = f"Todas as {batch.total_items} cotacoes falharam"
            else:
                batch.status = BatchJobStatus.COMPLETED

            logger.info(f"Batch {batch_job_id} finished: {completed} success, {failed} failed, {cancelled} cancelled")

            # Gerar arquivos de resultado (ZIP e Excel)
            try:
                from app.services.batch_result_generator import generate_batch_results
                generate_batch_results(db, batch_job_id)
            except Exception as e:
                logger.error(f"Error generating batch results for {batch_job_id}: {e}")

        db.commit()
    except Exception as e:
        logger.error(f"Error updating batch {batch_job_id}: {e}")
        db.rollback()
