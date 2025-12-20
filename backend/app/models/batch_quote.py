from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class BatchJobStatus(str, enum.Enum):
    """Status do job de lote"""
    PENDING = "PENDING"                     # Job criado, nao iniciado
    PROCESSING = "PROCESSING"               # Cotacoes sendo processadas
    COMPLETED = "COMPLETED"                 # Todas as cotacoes finalizadas
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"  # Algumas falharam/interrompidas
    ERROR = "ERROR"                         # Erro critico no nivel do lote
    CANCELLED = "CANCELLED"                 # Cancelado pelo usuario


class BatchQuoteJob(Base):
    """
    Modelo para gerenciar jobs de cotacao em lote.

    Um BatchQuoteJob agrupa multiplas QuoteRequests que foram
    criadas em uma unica operacao de lote (texto, imagens ou arquivo).
    """
    __tablename__ = "batch_quote_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Status do job de lote
    status = Column(SQLEnum(BatchJobStatus), default=BatchJobStatus.PENDING)

    # Tipo de entrada do lote (TEXT_BATCH, IMAGE_BATCH, FILE_BATCH)
    input_type = Column(String(50), nullable=False)

    # Vinculacao com projeto (opcional)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    config_version_id = Column(Integer, ForeignKey("project_config_versions.id"), nullable=True)

    # Metadados
    local = Column(String(200), nullable=True)
    pesquisador = Column(String(200), nullable=True)

    # Contadores de progresso
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)

    # Armazenamento da entrada original
    original_input_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)  # Para FILE_BATCH
    original_input_text = Column(Text, nullable=True)  # Para TEXT_BATCH (separado por ";")

    # Rastreamento de task Celery para retomada
    celery_task_id = Column(String(255), nullable=True, index=True)
    last_processed_index = Column(Integer, default=0)  # Para retomada

    # Mensagem de erro
    error_message = Column(Text, nullable=True)

    # Arquivos de resultado do lote
    result_zip_path = Column(String(500), nullable=True)  # ZIP com todos os PDFs
    result_excel_path = Column(String(500), nullable=True)  # Excel com resumo

    # Relationships
    project = relationship("Project")
    config_version = relationship("ProjectConfigVersion")
    original_input_file = relationship("File", foreign_keys=[original_input_file_id])
    quote_requests = relationship("QuoteRequest", back_populates="batch_job")
