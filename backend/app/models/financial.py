from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ApiCostConfig(Base):
    __tablename__ = "api_cost_config"

    id = Column(Integer, primary_key=True, index=True)
    api_name = Column(String(50), nullable=False)  # 'anthropic' ou 'serpapi'
    config_type = Column(String(50), nullable=False)  # 'model' ou 'subscription'
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))
    total_calls = Column(Integer)  # Para SERPAPI
    total_cost_brl = Column(Numeric(10, 2))  # Custo total pago
    cost_per_call_brl = Column(Numeric(10, 6))  # Custo por chamada (SERPAPI)
    cost_per_token_brl = Column(Numeric(10, 8))  # Custo por token (Anthropic)
    model_name = Column(String(100))  # Nome do modelo (para Anthropic)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    api_name = Column(String(50), nullable=False, index=True)
    quote_id = Column(Integer, ForeignKey("quote_requests.id", ondelete="CASCADE"))
    client_name = Column(String(255))
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    project_name = Column(String(255))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    user_name = Column(String(255))
    description = Column(Text)
    quantity = Column(Integer)  # Tokens ou chamadas
    unit_cost_brl = Column(Numeric(10, 8))
    total_cost_brl = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    quote = relationship("QuoteRequest", back_populates="financial_transactions")
    project = relationship("Project")
    user = relationship("User")
