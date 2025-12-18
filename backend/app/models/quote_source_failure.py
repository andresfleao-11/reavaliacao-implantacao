from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class CaptureFailureReason(str, enum.Enum):
    """Razoes para falha na captura de preco/screenshot"""
    TIMEOUT = "TIMEOUT"  # Timeout ao carregar pagina
    PRICE_MISMATCH = "PRICE_MISMATCH"  # Preco extraido diferente do Google Shopping
    PRICE_EXTRACTION_FAILED = "PRICE_EXTRACTION_FAILED"  # Nao conseguiu extrair preco
    INVALID_PRICE = "INVALID_PRICE"  # Preco invalido (None, <= 0, etc)
    PAGE_LOAD_ERROR = "PAGE_LOAD_ERROR"  # Erro ao carregar pagina
    SCREENSHOT_ERROR = "SCREENSHOT_ERROR"  # Erro ao capturar screenshot
    BLOCKED_BY_SITE = "BLOCKED_BY_SITE"  # Site bloqueou acesso (403, captcha, etc)
    NETWORK_ERROR = "NETWORK_ERROR"  # Erro de rede
    NO_STORE_LINK = "NO_STORE_LINK"  # Nao conseguiu obter link da loja via API
    BLOCKED_DOMAIN = "BLOCKED_DOMAIN"  # Dominio bloqueado (ex: leroymerlin.com.br)
    FOREIGN_DOMAIN = "FOREIGN_DOMAIN"  # Dominio estrangeiro (nao .br)
    LISTING_URL = "LISTING_URL"  # URL de listagem/busca em vez de produto
    DUPLICATE_URL = "DUPLICATE_URL"  # URL ja usada nesta cotacao
    OTHER = "OTHER"  # Outro erro


class QuoteSourceFailure(Base):
    """
    Registra tentativas falhas de captura de preco/screenshot de lojas.
    Permite diagnostico pos-facto de por que uma cotacao teve menos fontes do que o esperado.
    """
    __tablename__ = "quote_source_failures"

    id = Column(Integer, primary_key=True, index=True)
    quote_request_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=False, index=True)

    # Dados do produto/loja que falhou
    url = Column(Text, nullable=False)
    domain = Column(String(255), nullable=True, index=True)
    product_title = Column(Text, nullable=True)

    # Preco esperado do Google Shopping (para comparacao)
    google_price = Column(Numeric(12, 2), nullable=True)

    # Preco extraido do site (se conseguiu extrair antes de falhar)
    extracted_price = Column(Numeric(12, 2), nullable=True)

    # Razao da falha
    failure_reason = Column(SQLEnum(CaptureFailureReason), nullable=False, default=CaptureFailureReason.OTHER)

    # Mensagem de erro detalhada
    error_message = Column(Text, nullable=True)

    # Timestamps
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento
    quote_request = relationship("QuoteRequest", back_populates="capture_failures")
