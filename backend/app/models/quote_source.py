from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class ExtractionMethod(str, enum.Enum):
    JSONLD = "JSONLD"
    META = "META"
    DOM = "DOM"
    LLM = "LLM"


class QuoteSource(Base):
    __tablename__ = "quote_sources"

    id = Column(Integer, primary_key=True, index=True)
    quote_request_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=False, index=True)

    url = Column(Text, nullable=False)
    domain = Column(String(255), nullable=True, index=True)
    page_title = Column(Text, nullable=True)

    price_value = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), default="BRL")

    extraction_method = Column(SQLEnum(ExtractionMethod), nullable=True)

    screenshot_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)

    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    is_outlier = Column(Boolean, default=False)
    is_accepted = Column(Boolean, default=True)

    quote_request = relationship("QuoteRequest", back_populates="sources")
    screenshot = relationship("File", foreign_keys=[screenshot_file_id])
