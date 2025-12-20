"""
Endpoints de saude do sistema e recuperacao de cotacoes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import User
from app.services.checkpoint_manager import (
    find_stuck_quotes,
    find_resumable_quotes,
    reset_stuck_quote,
    get_processing_stats,
    CheckpointManager
)
from app.tasks.scheduled_tasks import recover_stuck_quotes, cleanup_old_processing
from app.tasks.quote_tasks import process_quote_request
from app.tasks.batch_tasks import process_batch_job
from app.models.quote_request import QuoteRequest, QuoteStatus
from app.models.batch_quote import BatchQuoteJob, BatchJobStatus

router = APIRouter(prefix="/api/system", tags=["System Health"])


@router.get("/health")
def health_check():
    """Health check basico do sistema."""
    return {"status": "healthy"}


@router.get("/processing-stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna estatisticas de processamento de cotacoes.

    Inclui:
    - Total em processamento
    - Quantidade travadas
    - Distribuicao por checkpoint
    - Tempo medio de processamento
    """
    stats = get_processing_stats(db)
    return stats


@router.get("/stuck-quotes")
def list_stuck_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lista cotacoes que estao travadas (PROCESSING sem heartbeat recente).
    """
    stuck = find_stuck_quotes(db)

    return {
        "count": len(stuck),
        "quotes": [
            {
                "id": q.id,
                "created_at": q.created_at.isoformat() if q.created_at else None,
                "checkpoint": q.processing_checkpoint,
                "last_heartbeat": q.last_heartbeat.isoformat() if q.last_heartbeat else None,
                "worker_id": q.worker_id,
                "batch_job_id": q.batch_job_id,
                "input_text": q.input_text[:100] if q.input_text else None
            }
            for q in stuck
        ]
    }


@router.post("/recover-stuck")
def trigger_recovery(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dispara recuperacao manual de cotacoes travadas.

    Identifica todas as cotacoes em PROCESSING sem heartbeat recente
    e as re-enfileira para processamento.
    """
    # Dispara task assincrona
    task = recover_stuck_quotes.delay()

    return {
        "message": "Recuperacao iniciada",
        "task_id": task.id
    }


@router.post("/recover-quote/{quote_id}")
def recover_single_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera uma cotacao especifica que esta travada.
    """
    quote = db.query(QuoteRequest).filter(QuoteRequest.id == quote_id).first()

    if not quote:
        raise HTTPException(status_code=404, detail="Cotacao nao encontrada")

    if quote.status != QuoteStatus.PROCESSING:
        raise HTTPException(
            status_code=400,
            detail=f"Cotacao nao esta em PROCESSING (status atual: {quote.status.value})"
        )

    # Reseta e re-enfileira
    reset_stuck_quote(db, quote)
    process_quote_request.delay(quote_id)

    return {
        "message": f"Cotacao {quote_id} re-enfileirada",
        "previous_checkpoint": quote.processing_checkpoint,
        "attempt_number": quote.attempt_number
    }


@router.post("/resume-batch/{batch_id}")
def resume_batch(
    batch_id: int,
    reset_errors: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retoma processamento de um lote que foi interrompido.

    Args:
        batch_id: ID do lote
        reset_errors: Se True, reseta cotacoes com ERROR para tentar novamente
    """
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    # Contar cotacoes pendentes
    pending_count = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch_id,
        QuoteRequest.status == QuoteStatus.PROCESSING
    ).count()

    error_count = 0
    if reset_errors:
        # Resetar cotacoes com erro
        error_quotes = db.query(QuoteRequest).filter(
            QuoteRequest.batch_job_id == batch_id,
            QuoteRequest.status == QuoteStatus.ERROR
        ).all()

        for q in error_quotes:
            q.status = QuoteStatus.PROCESSING
            q.error_message = None
            q.processing_checkpoint = None
            q.worker_id = None
            q.attempt_number = (q.attempt_number or 1) + 1
            error_count += 1

        db.commit()

    # Atualiza status do lote
    batch.status = BatchJobStatus.PROCESSING
    db.commit()

    # Dispara task de processamento do lote
    task = process_batch_job.delay(batch_id, resume=True)

    return {
        "message": f"Lote {batch_id} retomado",
        "task_id": task.id,
        "pending_quotes": pending_count,
        "reset_error_quotes": error_count
    }


@router.get("/batch-status/{batch_id}")
def get_batch_detailed_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna status detalhado de um lote, incluindo cotacoes travadas.
    """
    batch = db.query(BatchQuoteJob).filter(BatchQuoteJob.id == batch_id).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Lote nao encontrado")

    # Contar por status
    from sqlalchemy import func

    status_counts = dict(
        db.query(
            QuoteRequest.status,
            func.count(QuoteRequest.id)
        ).filter(
            QuoteRequest.batch_job_id == batch_id
        ).group_by(QuoteRequest.status).all()
    )

    # Cotacoes travadas neste lote
    from datetime import datetime, timedelta
    timeout = datetime.utcnow() - timedelta(minutes=10)

    stuck_in_batch = db.query(QuoteRequest).filter(
        QuoteRequest.batch_job_id == batch_id,
        QuoteRequest.status == QuoteStatus.PROCESSING,
        QuoteRequest.last_heartbeat < timeout
    ).count()

    # Checkpoint distribution
    checkpoint_counts = dict(
        db.query(
            QuoteRequest.processing_checkpoint,
            func.count(QuoteRequest.id)
        ).filter(
            QuoteRequest.batch_job_id == batch_id,
            QuoteRequest.status == QuoteStatus.PROCESSING
        ).group_by(QuoteRequest.processing_checkpoint).all()
    )

    return {
        "batch_id": batch_id,
        "batch_status": batch.status.value if batch.status else None,
        "total_items": batch.total_items,
        "completed_items": batch.completed_items,
        "failed_items": batch.failed_items,
        "status_distribution": {k.value if k else 'NULL': v for k, v in status_counts.items()},
        "stuck_quotes": stuck_in_batch,
        "checkpoint_distribution": checkpoint_counts,
        "progress_percentage": round(
            ((batch.completed_items or 0) + (batch.failed_items or 0)) / batch.total_items * 100, 2
        ) if batch.total_items else 0
    }


@router.post("/cleanup-old")
def trigger_cleanup(
    current_user: User = Depends(get_current_user)
):
    """
    Dispara limpeza manual de cotacoes antigas em PROCESSING.
    """
    task = cleanup_old_processing.delay()

    return {
        "message": "Limpeza iniciada",
        "task_id": task.id
    }
