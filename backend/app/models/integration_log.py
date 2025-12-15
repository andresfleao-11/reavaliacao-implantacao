from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class IntegrationLog(Base):
    """Log de chamadas para integrações externas (Anthropic, SerpAPI, etc)"""
    __tablename__ = "integration_logs"

    id = Column(Integer, primary_key=True, index=True)
    quote_request_id = Column(Integer, ForeignKey("quote_requests.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tipo de integração: 'anthropic' ou 'serpapi'
    integration_type = Column(String(50), nullable=False, index=True)

    # Para Anthropic
    model_used = Column(String(100), nullable=True)  # ex: claude-sonnet-4-20250514
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(10, 6), nullable=True)  # Custo estimado em USD

    # Para SerpAPI
    api_used = Column(String(100), nullable=True)  # ex: google_shopping
    search_url = Column(Text, nullable=True)  # URL da busca realizada
    product_link = Column(Text, nullable=True)  # Link do produto encontrado

    # Comum a ambos
    activity = Column(Text, nullable=True)  # Descrição da atividade
    request_data = Column(JSON, nullable=True)  # Dados da requisição (opcional)
    response_summary = Column(JSON, nullable=True)  # Resumo da resposta (opcional)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationship
    quote_request = relationship("QuoteRequest", back_populates="integration_logs")
