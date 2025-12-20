from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Numeric, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class QuoteStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    AWAITING_REVIEW = "AWAITING_REVIEW"  # Menos fontes que o parametro N


class QuoteInputType(str, enum.Enum):
    TEXT = "TEXT"           # Entrada por texto descritivo
    IMAGE = "IMAGE"         # Entrada por imagem (OCR)
    GOOGLE_LENS = "GOOGLE_LENS"  # Entrada via Google Lens
    TEXT_BATCH = "TEXT_BATCH"    # Lote via texto (separado por ";")
    IMAGE_BATCH = "IMAGE_BATCH"  # Lote via imagens
    FILE_BATCH = "FILE_BATCH"    # Lote via arquivo CSV/XLSX


class ValidationStatus(str, enum.Enum):
    """Status de validação de um produto durante processamento"""
    PENDING = "PENDING"      # Ainda não validado
    VALID = "VALID"          # Validado com sucesso
    FAILED = "FAILED"        # Falhou na validação


class FailureReason(str, enum.Enum):
    """Motivo de falha na validação de um produto"""
    NO_STORE_LINK = "NO_STORE_LINK"        # API não retornou link de loja
    BLOCKED_DOMAIN = "BLOCKED_DOMAIN"      # Domínio bloqueado
    FOREIGN_DOMAIN = "FOREIGN_DOMAIN"      # Domínio estrangeiro (não .br)
    DUPLICATE_DOMAIN = "DUPLICATE_DOMAIN"  # Domínio já usado nesta cotação
    LISTING_URL = "LISTING_URL"            # URL de listagem/busca
    EXTRACTION_ERROR = "EXTRACTION_ERROR"  # Erro ao extrair preço
    PRICE_MISMATCH = "PRICE_MISMATCH"      # Preço do site ≠ Google Shopping


class BlockStatus(str, enum.Enum):
    """Status de um bloco de variação durante processamento"""
    PENDING = "PENDING"        # Bloco não processado
    PROCESSING = "PROCESSING"  # Bloco em processamento
    VALID = "VALID"            # Bloco atingiu meta de cotações
    FAILED = "FAILED"          # Bloco não conseguiu atingir meta


class QuoteRequest(Base):
    __tablename__ = "quote_requests"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(SQLEnum(QuoteStatus), default=QuoteStatus.PROCESSING)
    input_type = Column(SQLEnum(QuoteInputType), default=QuoteInputType.TEXT)  # Tipo de entrada

    # Vinculação com projeto (opcional)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)

    # Vinculação com versão de configuração do projeto
    config_version_id = Column(Integer, ForeignKey("project_config_versions.id"), nullable=True, index=True)

    input_text = Column(Text, nullable=True)
    codigo_item = Column(String(100), nullable=True, index=True)

    claude_payload_json = Column(JSON, nullable=True)
    search_query_final = Column(Text, nullable=True)

    local = Column(String(200), nullable=True)
    pesquisador = Column(String(200), nullable=True)

    valor_medio = Column(Numeric(12, 2), nullable=True)
    valor_minimo = Column(Numeric(12, 2), nullable=True)
    valor_maximo = Column(Numeric(12, 2), nullable=True)
    variacao_percentual = Column(Numeric(8, 4), nullable=True)  # Variação = (MAX/MIN - 1) * 100

    error_message = Column(Text, nullable=True)

    # Campos de progresso
    current_step = Column(String(100), nullable=True)  # Ex: "analyzing_image", "searching_prices"
    progress_percentage = Column(Integer, default=0)  # 0-100
    step_details = Column(Text, nullable=True)  # Detalhes da etapa atual

    # Campos de tentativas (para rastrear recotações)
    attempt_number = Column(Integer, default=1)  # Número da tentativa (1, 2, 3, ...)
    original_quote_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=True)  # ID da cotação original

    # Campos de lote
    batch_job_id = Column(Integer, ForeignKey("batch_quote_jobs.id"), nullable=True, index=True)
    batch_index = Column(Integer, nullable=True)  # Posição no lote (para ordenação/retomada)

    # Cache de resposta do Google Shopping (para retomada de processamento)
    google_shopping_response_json = Column(JSON, nullable=True)  # Resposta completa da API
    shopping_response_saved_at = Column(DateTime(timezone=True), nullable=True)

    # Sistema de checkpoints para retomada
    processing_checkpoint = Column(String(50), nullable=True)  # Etapa atual: INIT, AI_ANALYSIS, SHOPPING_SEARCH, PRICE_EXTRACTION, FINALIZATION
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)  # Ultimo sinal de vida do worker
    worker_id = Column(String(100), nullable=True)  # ID do worker que esta processando
    resume_data = Column(JSON, nullable=True)  # Dados necessarios para retomar (produtos ja testados, etc)
    started_at = Column(DateTime(timezone=True), nullable=True)  # Quando iniciou processamento
    completed_at = Column(DateTime(timezone=True), nullable=True)  # Quando finalizou

    sources = relationship("QuoteSource", back_populates="quote_request", cascade="all, delete-orphan")
    input_images = relationship("File", foreign_keys="[File.quote_request_id]",
                                primaryjoin="and_(File.quote_request_id==QuoteRequest.id, File.type=='INPUT_IMAGE')")
    documents = relationship("GeneratedDocument", back_populates="quote_request", cascade="all, delete-orphan")
    project = relationship("Project", back_populates="cotacoes")
    config_version = relationship("ProjectConfigVersion", back_populates="cotacoes")
    financial_transactions = relationship("FinancialTransaction", back_populates="quote", cascade="all, delete-orphan")
    integration_logs = relationship("IntegrationLog", back_populates="quote_request", cascade="all, delete-orphan")
    batch_job = relationship("BatchQuoteJob", back_populates="quote_requests")
    capture_failures = relationship("QuoteSourceFailure", back_populates="quote_request", cascade="all, delete-orphan")
