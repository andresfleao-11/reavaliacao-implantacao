from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.database import get_db
from app.models.financial import ApiCostConfig, FinancialTransaction
from app.schemas.financial import (
    ApiCostConfigCreate,
    ApiCostConfigUpdate,
    ApiCostConfig as ApiCostConfigSchema,
    FinancialTransactionCreate,
    FinancialTransaction as FinancialTransactionSchema,
    FinancialSummary,
    FinancialReportFilters
)

router = APIRouter(prefix="/api/financial", tags=["financial"])


# API Cost Config Endpoints
@router.post("/api-config", response_model=ApiCostConfigSchema)
def create_api_config(config: ApiCostConfigCreate, db: Session = Depends(get_db)):
    """Criar nova configuração de custo de API"""
    # Desativar configurações anteriores do mesmo tipo
    db.query(ApiCostConfig).filter(
        and_(
            ApiCostConfig.api_name == config.api_name,
            ApiCostConfig.config_type == config.config_type,
            ApiCostConfig.is_active == True
        )
    ).update({"is_active": False})

    db_config = ApiCostConfig(**config.dict())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.get("/api-config", response_model=List[ApiCostConfigSchema])
def list_api_configs(
    api_name: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """Listar configurações de custo de APIs"""
    query = db.query(ApiCostConfig)

    if api_name:
        query = query.filter(ApiCostConfig.api_name == api_name)
    if is_active is not None:
        query = query.filter(ApiCostConfig.is_active == is_active)

    return query.order_by(ApiCostConfig.created_at.desc()).all()


@router.get("/api-config/active", response_model=List[ApiCostConfigSchema])
def get_active_configs(db: Session = Depends(get_db)):
    """Obter configurações ativas de todas as APIs"""
    return db.query(ApiCostConfig).filter(
        ApiCostConfig.is_active == True
    ).all()


@router.patch("/api-config/{config_id}", response_model=ApiCostConfigSchema)
def update_api_config(
    config_id: int,
    config: ApiCostConfigUpdate,
    db: Session = Depends(get_db)
):
    """Atualizar configuração de custo"""
    db_config = db.query(ApiCostConfig).filter(ApiCostConfig.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")

    for key, value in config.dict(exclude_unset=True).items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)
    return db_config


# Financial Transactions Endpoints
@router.post("/transactions", response_model=FinancialTransactionSchema)
def create_transaction(transaction: FinancialTransactionCreate, db: Session = Depends(get_db)):
    """Criar nova transação financeira"""
    db_transaction = FinancialTransaction(**transaction.dict())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.get("/transactions", response_model=List[FinancialTransactionSchema])
def list_transactions(
    project_id: Optional[int] = None,
    api_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Listar transações financeiras com filtros"""
    query = db.query(FinancialTransaction)

    if project_id:
        query = query.filter(FinancialTransaction.project_id == project_id)
    if api_name:
        query = query.filter(FinancialTransaction.api_name == api_name)
    if start_date:
        query = query.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(FinancialTransaction.transaction_date <= end_date)

    return query.order_by(FinancialTransaction.transaction_date.desc()).offset(offset).limit(limit).all()


@router.get("/report", response_model=dict)
def get_financial_report(
    period: Optional[str] = None,
    month_ref: Optional[str] = None,
    project_id: Optional[int] = None,
    api_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Gerar relatório financeiro com filtros"""
    query = db.query(FinancialTransaction)

    # Aplicar filtros de período
    if period:
        days = int(period.replace('d', ''))
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
    elif month_ref:
        # Formato: ago25, dez25, jan26
        month_map = {
            'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
        }
        month_str = month_ref[:3].lower()
        year = int('20' + month_ref[3:])
        month = month_map.get(month_str, 1)

        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)

    if start_date:
        query = query.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(FinancialTransaction.transaction_date <= end_date)
    if project_id:
        query = query.filter(FinancialTransaction.project_id == project_id)
    if api_name:
        query = query.filter(FinancialTransaction.api_name == api_name)

    transactions = query.order_by(FinancialTransaction.transaction_date.desc()).all()

    # Calcular totais
    total_cost = sum(t.total_cost_brl for t in transactions)
    anthropic_cost = sum(t.total_cost_brl for t in transactions if t.api_name == 'anthropic')
    serpapi_cost = sum(t.total_cost_brl for t in transactions if t.api_name == 'serpapi')

    # Obter configurações ativas
    active_configs = db.query(ApiCostConfig).filter(ApiCostConfig.is_active == True).all()

    return {
        "summary": {
            "total_cost": float(total_cost),
            "anthropic_cost": float(anthropic_cost),
            "serpapi_cost": float(serpapi_cost),
            "total_transactions": len(transactions),
            "period_start": start_date,
            "period_end": end_date
        },
        "active_configs": [
            {
                "api_name": c.api_name,
                "model_name": c.model_name,
                "cost_per_token": float(c.cost_per_token_brl) if c.cost_per_token_brl else None,
                "cost_per_call": float(c.cost_per_call_brl) if c.cost_per_call_brl else None,
            }
            for c in active_configs
        ],
        "transactions": [
            {
                "id": t.id,
                "transaction_date": t.transaction_date,
                "api_name": t.api_name,
                "quote_id": t.quote_id,
                "client_name": t.client_name,
                "project_name": t.project_name,
                "user_name": t.user_name,
                "description": t.description,
                "total_cost_brl": float(t.total_cost_brl)
            }
            for t in transactions
        ]
    }


@router.get("/quote/{quote_id}/costs")
def get_quote_costs(quote_id: int, db: Session = Depends(get_db)):
    """Obter custos financeiros de uma cotação específica com valores em USD e BRL"""
    from app.models import Setting, IntegrationLog

    # Buscar configuração de taxa de câmbio e custo SerpAPI
    cost_config = db.query(Setting).filter(Setting.key == "cost_config").first()
    usd_to_brl_rate = 6.0  # Default rate
    serpapi_cost_per_call = 0.0

    if cost_config and cost_config.value_json:
        usd_to_brl_rate = cost_config.value_json.get("usd_to_brl_rate", 6.0) or 6.0
        serpapi_cost_per_call = cost_config.value_json.get("serpapi_cost_per_call", 0.0) or 0.0

    # Buscar logs de integração para custos em USD (Anthropic)
    integration_logs = db.query(IntegrationLog).filter(
        IntegrationLog.quote_request_id == quote_id
    ).all()

    # Calcular custo Anthropic em USD a partir dos logs
    anthropic_cost_usd = sum(
        float(log.estimated_cost_usd or 0)
        for log in integration_logs
        if log.integration_type == 'anthropic' and log.estimated_cost_usd
    )

    # Converter para BRL
    anthropic_cost_brl = anthropic_cost_usd * usd_to_brl_rate

    # Calcular custo SerpAPI em BRL (já é em BRL)
    serpapi_calls = sum(
        1 for log in integration_logs
        if log.integration_type == 'serpapi'
    )
    serpapi_cost_brl = serpapi_calls * serpapi_cost_per_call

    total_cost_usd = anthropic_cost_usd  # SerpAPI não tem custo em USD
    total_cost_brl = anthropic_cost_brl + serpapi_cost_brl

    return {
        "quote_id": quote_id,
        "usd_to_brl_rate": usd_to_brl_rate,
        "anthropic_cost_usd": anthropic_cost_usd,
        "anthropic_cost_brl": anthropic_cost_brl,
        "serpapi_calls": serpapi_calls,
        "serpapi_cost_per_call": serpapi_cost_per_call,
        "serpapi_cost_brl": serpapi_cost_brl,
        "total_cost_usd": total_cost_usd,
        "total_cost_brl": total_cost_brl
    }


@router.get("/summary", response_model=FinancialSummary)
def get_summary(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Obter resumo financeiro"""
    query = db.query(
        func.sum(FinancialTransaction.total_cost_brl).label('total'),
        func.count(FinancialTransaction.id).label('count')
    )

    if start_date:
        query = query.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(FinancialTransaction.transaction_date <= end_date)

    result = query.first()

    # Totais por API
    anthropic_total = db.query(func.sum(FinancialTransaction.total_cost_brl)).filter(
        FinancialTransaction.api_name == 'anthropic'
    )
    if start_date:
        anthropic_total = anthropic_total.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        anthropic_total = anthropic_total.filter(FinancialTransaction.transaction_date <= end_date)

    serpapi_total = db.query(func.sum(FinancialTransaction.total_cost_brl)).filter(
        FinancialTransaction.api_name == 'serpapi'
    )
    if start_date:
        serpapi_total = serpapi_total.filter(FinancialTransaction.transaction_date >= start_date)
    if end_date:
        serpapi_total = serpapi_total.filter(FinancialTransaction.transaction_date <= end_date)

    return {
        "total_cost": result.total or 0,
        "anthropic_cost": anthropic_total.scalar() or 0,
        "serpapi_cost": serpapi_total.scalar() or 0,
        "total_transactions": result.count or 0,
        "period_start": start_date or datetime.now(),
        "period_end": end_date or datetime.now()
    }
