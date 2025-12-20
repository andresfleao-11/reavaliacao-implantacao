"""
Gerenciador de Checkpoints para Cotacoes.

Sistema que permite:
- Salvar estado de processamento em pontos especificos
- Detectar cotacoes travadas (zombie detection)
- Retomar processamento de onde parou
- Garantir integridade do fluxo de etapas
"""
import logging
import socket
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.quote_request import QuoteRequest, QuoteStatus

logger = logging.getLogger(__name__)


class ProcessingCheckpoint:
    """Constantes para checkpoints de processamento."""
    INIT = "INIT"                           # Inicio do processamento
    AI_ANALYSIS_START = "AI_ANALYSIS_START" # Iniciou analise IA
    AI_ANALYSIS_DONE = "AI_ANALYSIS_DONE"   # Analise IA concluida
    FIPE_SEARCH = "FIPE_SEARCH"             # Buscando FIPE (veiculos)
    FIPE_DONE = "FIPE_DONE"                 # FIPE concluido
    SHOPPING_SEARCH_START = "SHOPPING_SEARCH_START"  # Iniciou busca Google Shopping
    SHOPPING_SEARCH_DONE = "SHOPPING_SEARCH_DONE"    # Busca Shopping concluida
    PRICE_EXTRACTION_START = "PRICE_EXTRACTION_START"  # Iniciou extracao de precos
    PRICE_EXTRACTION_PROGRESS = "PRICE_EXTRACTION_PROGRESS"  # Em progresso (com dados parciais)
    PRICE_EXTRACTION_DONE = "PRICE_EXTRACTION_DONE"    # Extracao concluida
    FINALIZATION = "FINALIZATION"           # Finalizando (calculando medias, etc)
    COMPLETED = "COMPLETED"                 # Processamento completo


# Mapeamento de checkpoint para proximo passo
CHECKPOINT_FLOW = {
    ProcessingCheckpoint.INIT: ProcessingCheckpoint.AI_ANALYSIS_START,
    ProcessingCheckpoint.AI_ANALYSIS_START: ProcessingCheckpoint.AI_ANALYSIS_DONE,
    ProcessingCheckpoint.AI_ANALYSIS_DONE: ProcessingCheckpoint.SHOPPING_SEARCH_START,  # ou FIPE_SEARCH
    ProcessingCheckpoint.FIPE_SEARCH: ProcessingCheckpoint.FIPE_DONE,
    ProcessingCheckpoint.FIPE_DONE: ProcessingCheckpoint.FINALIZATION,
    ProcessingCheckpoint.SHOPPING_SEARCH_START: ProcessingCheckpoint.SHOPPING_SEARCH_DONE,
    ProcessingCheckpoint.SHOPPING_SEARCH_DONE: ProcessingCheckpoint.PRICE_EXTRACTION_START,
    ProcessingCheckpoint.PRICE_EXTRACTION_START: ProcessingCheckpoint.PRICE_EXTRACTION_PROGRESS,
    ProcessingCheckpoint.PRICE_EXTRACTION_PROGRESS: ProcessingCheckpoint.PRICE_EXTRACTION_DONE,
    ProcessingCheckpoint.PRICE_EXTRACTION_DONE: ProcessingCheckpoint.FINALIZATION,
    ProcessingCheckpoint.FINALIZATION: ProcessingCheckpoint.COMPLETED,
}

# Tempo maximo sem heartbeat antes de considerar cotacao travada (em minutos)
HEARTBEAT_TIMEOUT_MINUTES = 10

# Tempo maximo de processamento total (em minutos)
MAX_PROCESSING_TIME_MINUTES = 30


def get_worker_id() -> str:
    """Gera um ID unico para o worker atual."""
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{hostname}-{pid}"


class CheckpointManager:
    """Gerenciador de checkpoints para cotacoes."""

    def __init__(self, db: Session):
        self.db = db
        self.worker_id = get_worker_id()

    def start_processing(self, quote: QuoteRequest) -> None:
        """
        Marca inicio do processamento de uma cotacao.
        Deve ser chamado no inicio de process_quote_request.
        """
        now = datetime.utcnow()
        quote.processing_checkpoint = ProcessingCheckpoint.INIT
        quote.last_heartbeat = now
        quote.worker_id = self.worker_id
        quote.started_at = now
        quote.resume_data = {}
        self.db.commit()
        logger.debug(f"Cotacao {quote.id}: Iniciou processamento (worker={self.worker_id})")

    def save_checkpoint(
        self,
        quote: QuoteRequest,
        checkpoint: str,
        resume_data: Optional[Dict[str, Any]] = None,
        progress_percentage: Optional[int] = None
    ) -> None:
        """
        Salva um checkpoint de processamento.

        Args:
            quote: Cotacao sendo processada
            checkpoint: Identificador do checkpoint (usar ProcessingCheckpoint)
            resume_data: Dados necessarios para retomar deste ponto
            progress_percentage: Porcentagem de progresso (0-100)
        """
        now = datetime.utcnow()
        quote.processing_checkpoint = checkpoint
        quote.last_heartbeat = now

        if resume_data:
            # Mescla com dados existentes para nao perder informacao
            existing = quote.resume_data or {}
            existing.update(resume_data)
            quote.resume_data = existing

        if progress_percentage is not None:
            quote.progress_percentage = progress_percentage

        self.db.commit()
        logger.debug(f"Cotacao {quote.id}: Checkpoint {checkpoint} (progress={progress_percentage}%)")

    def update_heartbeat(self, quote: QuoteRequest) -> None:
        """
        Atualiza o heartbeat da cotacao.
        Deve ser chamado periodicamente durante processamento longo.
        """
        quote.last_heartbeat = datetime.utcnow()
        self.db.commit()

    def complete_processing(self, quote: QuoteRequest, status: QuoteStatus) -> None:
        """
        Marca o processamento como completo.
        """
        now = datetime.utcnow()
        quote.processing_checkpoint = ProcessingCheckpoint.COMPLETED
        quote.last_heartbeat = now
        quote.completed_at = now
        quote.status = status
        quote.worker_id = None  # Libera o worker
        self.db.commit()
        logger.info(f"Cotacao {quote.id}: Processamento completo (status={status.value})")

    def fail_processing(self, quote: QuoteRequest, error_message: str) -> None:
        """
        Marca o processamento como falho.
        """
        now = datetime.utcnow()
        quote.last_heartbeat = now
        quote.completed_at = now
        quote.status = QuoteStatus.ERROR
        quote.error_message = error_message[:1000] if error_message else "Erro desconhecido"
        quote.worker_id = None
        self.db.commit()
        logger.error(f"Cotacao {quote.id}: Processamento falhou - {error_message[:100]}")

    def can_resume(self, quote: QuoteRequest) -> bool:
        """
        Verifica se uma cotacao pode ser retomada.

        Returns:
            True se a cotacao pode ser retomada de um checkpoint.
        """
        if quote.status != QuoteStatus.PROCESSING:
            return False

        # Precisa ter checkpoint salvo
        if not quote.processing_checkpoint:
            return False

        # Nao pode estar sendo processada por outro worker ativo
        if quote.worker_id and quote.last_heartbeat:
            timeout = datetime.utcnow() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
            if quote.last_heartbeat > timeout:
                # Worker ainda ativo
                return False

        return True

    def get_resume_checkpoint(self, quote: QuoteRequest) -> Optional[str]:
        """
        Retorna o checkpoint de onde retomar o processamento.
        Pode retornar um checkpoint anterior se o atual nao tiver dados suficientes.
        """
        checkpoint = quote.processing_checkpoint
        resume_data = quote.resume_data or {}

        # Se tem analise IA salva, pode pular para shopping ou price extraction
        if quote.claude_payload_json:
            if checkpoint in [ProcessingCheckpoint.AI_ANALYSIS_START, ProcessingCheckpoint.AI_ANALYSIS_DONE]:
                # Verifica se e veiculo para ir para FIPE ou Shopping
                natureza = quote.claude_payload_json.get("natureza", "")
                if natureza.startswith("veiculo_"):
                    return ProcessingCheckpoint.FIPE_SEARCH
                return ProcessingCheckpoint.SHOPPING_SEARCH_START

        # Se tem resposta do Google Shopping salva, pode pular para extracao
        if quote.google_shopping_response_json:
            if checkpoint in [ProcessingCheckpoint.SHOPPING_SEARCH_START, ProcessingCheckpoint.SHOPPING_SEARCH_DONE]:
                return ProcessingCheckpoint.PRICE_EXTRACTION_START

        # Se tem produtos ja testados, continua extracao
        if resume_data.get("tested_products"):
            if checkpoint == ProcessingCheckpoint.PRICE_EXTRACTION_PROGRESS:
                return ProcessingCheckpoint.PRICE_EXTRACTION_PROGRESS

        return checkpoint

    def claim_for_processing(self, quote: QuoteRequest) -> bool:
        """
        Tenta "reclamar" uma cotacao para processamento.
        Usa lock otimista para evitar que dois workers processem a mesma cotacao.

        Returns:
            True se conseguiu reclamar, False se outro worker ja reclamou.
        """
        now = datetime.utcnow()

        # Verifica se outro worker ja reclamou recentemente
        if quote.worker_id and quote.last_heartbeat:
            timeout = datetime.utcnow() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
            if quote.last_heartbeat > timeout and quote.worker_id != self.worker_id:
                logger.warning(f"Cotacao {quote.id}: Ja sendo processada por {quote.worker_id}")
                return False

        # Reclama a cotacao
        quote.worker_id = self.worker_id
        quote.last_heartbeat = now
        self.db.commit()

        # Verifica se realmente conseguiu (outro worker pode ter feito o mesmo)
        self.db.refresh(quote)
        if quote.worker_id != self.worker_id:
            logger.warning(f"Cotacao {quote.id}: Perdeu race condition para {quote.worker_id}")
            return False

        logger.info(f"Cotacao {quote.id}: Reclamada por {self.worker_id}")
        return True


def find_stuck_quotes(db: Session, timeout_minutes: int = HEARTBEAT_TIMEOUT_MINUTES) -> List[QuoteRequest]:
    """
    Encontra cotacoes que estao travadas (PROCESSING mas sem heartbeat recente).

    Args:
        db: Sessao do banco de dados
        timeout_minutes: Minutos sem heartbeat para considerar travada

    Returns:
        Lista de cotacoes travadas.
    """
    timeout = datetime.utcnow() - timedelta(minutes=timeout_minutes)

    stuck = db.query(QuoteRequest).filter(
        and_(
            QuoteRequest.status == QuoteStatus.PROCESSING,
            QuoteRequest.last_heartbeat < timeout
        )
    ).all()

    return stuck


def find_resumable_quotes(db: Session, limit: int = 100) -> List[QuoteRequest]:
    """
    Encontra cotacoes que podem ser retomadas.

    Criterios:
    - Status PROCESSING
    - Tem checkpoint salvo
    - Heartbeat expirado (worker morreu) OU sem worker

    Args:
        db: Sessao do banco de dados
        limit: Numero maximo de cotacoes a retornar

    Returns:
        Lista de cotacoes que podem ser retomadas.
    """
    timeout = datetime.utcnow() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)

    resumable = db.query(QuoteRequest).filter(
        and_(
            QuoteRequest.status == QuoteStatus.PROCESSING,
            QuoteRequest.processing_checkpoint.isnot(None),
            # Worker morreu (heartbeat expirado) ou nao tem worker
            ((QuoteRequest.last_heartbeat < timeout) | (QuoteRequest.worker_id.is_(None)))
        )
    ).order_by(QuoteRequest.created_at).limit(limit).all()

    return resumable


def reset_stuck_quote(db: Session, quote: QuoteRequest) -> None:
    """
    Reseta uma cotacao travada para que possa ser retomada.

    Args:
        db: Sessao do banco de dados
        quote: Cotacao a resetar
    """
    logger.info(f"Resetando cotacao travada {quote.id} (ultimo checkpoint: {quote.processing_checkpoint})")

    # Limpa o worker para permitir que outro processo
    quote.worker_id = None
    quote.last_heartbeat = None

    # Incrementa tentativa se estava em andamento
    quote.attempt_number = (quote.attempt_number or 1) + 1

    db.commit()


def get_processing_stats(db: Session) -> Dict[str, Any]:
    """
    Retorna estatisticas de processamento.

    Returns:
        Dict com estatisticas:
        - total_processing: Total em processamento
        - stuck_count: Quantidade travadas
        - by_checkpoint: Contagem por checkpoint
        - avg_processing_time: Tempo medio de processamento (segundos)
    """
    from sqlalchemy import func

    # Total em processamento
    total_processing = db.query(func.count(QuoteRequest.id)).filter(
        QuoteRequest.status == QuoteStatus.PROCESSING
    ).scalar()

    # Travadas
    timeout = datetime.utcnow() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
    stuck_count = db.query(func.count(QuoteRequest.id)).filter(
        and_(
            QuoteRequest.status == QuoteStatus.PROCESSING,
            QuoteRequest.last_heartbeat < timeout
        )
    ).scalar()

    # Por checkpoint
    by_checkpoint = dict(
        db.query(
            QuoteRequest.processing_checkpoint,
            func.count(QuoteRequest.id)
        ).filter(
            QuoteRequest.status == QuoteStatus.PROCESSING
        ).group_by(QuoteRequest.processing_checkpoint).all()
    )

    # Tempo medio (ultimas 100 concluidas)
    completed_quotes = db.query(QuoteRequest).filter(
        and_(
            QuoteRequest.status.in_([QuoteStatus.DONE, QuoteStatus.AWAITING_REVIEW]),
            QuoteRequest.started_at.isnot(None),
            QuoteRequest.completed_at.isnot(None)
        )
    ).order_by(QuoteRequest.completed_at.desc()).limit(100).all()

    avg_time = 0
    if completed_quotes:
        times = [(q.completed_at - q.started_at).total_seconds() for q in completed_quotes]
        avg_time = sum(times) / len(times)

    return {
        "total_processing": total_processing,
        "stuck_count": stuck_count,
        "by_checkpoint": by_checkpoint,
        "avg_processing_time_seconds": round(avg_time, 2)
    }
