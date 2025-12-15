from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(Integer, primary_key=True, index=True)
    quote_request_id = Column(Integer, ForeignKey("quote_requests.id"), nullable=False, index=True)
    pdf_file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    quote_request = relationship("QuoteRequest", back_populates="documents")
    pdf_file = relationship("File")
