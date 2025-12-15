from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ApiCostConfigBase(BaseModel):
    api_name: str = Field(..., description="Nome da API (anthropic ou serpapi)")
    config_type: str = Field(..., description="Tipo de configuração (model ou subscription)")
    start_date: datetime
    end_date: Optional[datetime] = None
    total_calls: Optional[int] = None
    total_cost_brl: Optional[Decimal] = None
    cost_per_call_brl: Optional[Decimal] = None
    cost_per_token_brl: Optional[Decimal] = None
    model_name: Optional[str] = None


class ApiCostConfigCreate(ApiCostConfigBase):
    pass


class ApiCostConfigUpdate(BaseModel):
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class ApiCostConfig(ApiCostConfigBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FinancialTransactionBase(BaseModel):
    api_name: str
    quote_id: Optional[int] = None
    client_name: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    unit_cost_brl: Optional[Decimal] = None
    total_cost_brl: Decimal


class FinancialTransactionCreate(FinancialTransactionBase):
    pass


class FinancialTransaction(FinancialTransactionBase):
    id: int
    transaction_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class FinancialSummary(BaseModel):
    total_cost: Decimal
    anthropic_cost: Decimal
    serpapi_cost: Decimal
    total_transactions: int
    period_start: datetime
    period_end: datetime


class FinancialReportFilters(BaseModel):
    period: Optional[str] = None  # '7d', '15d', '30d'
    month_ref: Optional[str] = None  # 'ago25', 'dez25', etc
    project_id: Optional[int] = None
    api_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
