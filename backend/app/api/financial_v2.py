"""
Módulo Financeiro V2 - API de consulta de custos baseada em IntegrationLog

Este módulo consulta diretamente os logs de integração para gerar relatórios
financeiros, sem necessidade de tabela de transações separada.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel
from enum import Enum

from app.core.database import get_db
from app.models import IntegrationLog, QuoteRequest, Project, Client, Setting, User


router = APIRouter(prefix="/api/v2/financial", tags=["financial-v2"])


# =====================
# Schemas
# =====================

class PeriodType(str, Enum):
    DAYS_7 = "7d"
    DAYS_15 = "15d"
    DAYS_30 = "30d"
    SPECIFIC = "specific"
    MONTH_REF = "month"


class IntegrationType(str, Enum):
    ANTHROPIC = "anthropic"
    SERPAPI = "serpapi"
    OPENAI = "openai"


class FinancialFilters(BaseModel):
    period: Optional[PeriodType] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    month_ref: Optional[str] = None  # Formato: "dez24", "jan25"
    integrations: Optional[List[IntegrationType]] = None
    project_id: Optional[int] = None


class TransactionItem(BaseModel):
    date: datetime
    api: str
    quote_id: int
    client_name: Optional[str]
    project_name: Optional[str]
    user_name: Optional[str]
    description: str
    cost_usd: float
    cost_brl: float
    request_data: Optional[dict] = None


class IntegrationTotal(BaseModel):
    api: str
    total_usd: float
    total_brl: float
    transaction_count: int


class FinancialReportResponse(BaseModel):
    total_usd: float
    total_brl: float
    totals_by_integration: List[IntegrationTotal]
    transactions: List[TransactionItem]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    usd_to_brl_rate: float


class MonthOption(BaseModel):
    value: str  # "dez24"
    label: str  # "Dezembro 2024"


# =====================
# Helper Functions
# =====================

def get_cost_config(db: Session) -> dict:
    """Obtém configurações de custo (taxa de câmbio, custo por chamada SerpAPI)"""
    setting = db.query(Setting).filter(Setting.key == "cost_config").first()

    defaults = {
        "usd_to_brl_rate": 6.0,
        "serpapi_cost_per_call": 0.0
    }

    if setting and setting.value_json:
        return {
            "usd_to_brl_rate": setting.value_json.get("usd_to_brl_rate") or defaults["usd_to_brl_rate"],
            "serpapi_cost_per_call": setting.value_json.get("serpapi_cost_per_call") or defaults["serpapi_cost_per_call"]
        }

    return defaults


def parse_period(period: PeriodType, month_ref: str = None,
                 start_date: datetime = None, end_date: datetime = None) -> tuple:
    """Converte parâmetros de período em start_date e end_date"""

    if period == PeriodType.DAYS_7:
        end = datetime.now()
        start = end - timedelta(days=7)
    elif period == PeriodType.DAYS_15:
        end = datetime.now()
        start = end - timedelta(days=15)
    elif period == PeriodType.DAYS_30:
        end = datetime.now()
        start = end - timedelta(days=30)
    elif period == PeriodType.MONTH_REF and month_ref:
        # Formato: "dez24", "jan25"
        month_map = {
            'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
        }
        month_str = month_ref[:3].lower()
        year = int('20' + month_ref[3:])
        month = month_map.get(month_str, 1)

        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(seconds=1)
    elif period == PeriodType.SPECIFIC and start_date and end_date:
        start = start_date
        end = end_date
    else:
        return None, None

    return start, end


def build_transaction_description(logs: List[IntegrationLog]) -> str:
    """Constrói a descrição da transação baseada nos logs de integração"""

    # Separar por tipo
    anthropic_logs = [l for l in logs if l.integration_type == 'anthropic']
    serpapi_logs = [l for l in logs if l.integration_type == 'serpapi']
    openai_logs = [l for l in logs if l.integration_type == 'openai']

    parts = []

    # Anthropic - total de tokens
    if anthropic_logs:
        total_tokens = sum(l.total_tokens or 0 for l in anthropic_logs)
        parts.append(f"{total_tokens:,} tokens".replace(",", "."))

    # OpenAI - total de tokens
    if openai_logs:
        total_tokens = sum(l.total_tokens or 0 for l in openai_logs)
        parts.append(f"{total_tokens:,} tokens".replace(",", "."))

    # SerpAPI - contagem por tipo de busca
    if serpapi_logs:
        shopping_calls = sum(1 for l in serpapi_logs if l.api_used == 'google_shopping')
        immersive_calls = sum(1 for l in serpapi_logs if l.api_used == 'google_immersive_product')

        serpapi_parts = []
        if shopping_calls > 0:
            serpapi_parts.append(f"{shopping_calls} chamada{'s' if shopping_calls > 1 else ''} Busca de preço (Google Shopping)")
        if immersive_calls > 0:
            serpapi_parts.append(f"{immersive_calls} chamada{'s' if immersive_calls > 1 else ''} Busca de loja (Google Immersive)")

        if serpapi_parts:
            parts.append(" + ".join(serpapi_parts))

    return " | ".join(parts) if parts else "Sem detalhes"


def aggregate_logs_by_quote(logs: List[IntegrationLog], cost_config: dict) -> dict:
    """Agrupa logs por cotação e calcula custos"""

    usd_to_brl = cost_config["usd_to_brl_rate"]
    serpapi_cost = cost_config["serpapi_cost_per_call"]

    by_quote = {}

    for log in logs:
        # Ignorar logs que não são integrações de API
        if log.integration_type not in ('anthropic', 'openai', 'serpapi'):
            continue

        quote_id = log.quote_request_id
        if quote_id not in by_quote:
            by_quote[quote_id] = {
                "logs": [],
                "cost_usd": 0.0,
                "cost_brl": 0.0,
                "apis": set()
            }

        by_quote[quote_id]["logs"].append(log)
        by_quote[quote_id]["apis"].add(log.integration_type)

        # Calcular custo
        if log.integration_type in ('anthropic', 'openai'):
            cost_usd = float(log.estimated_cost_usd or 0)
            by_quote[quote_id]["cost_usd"] += cost_usd
            by_quote[quote_id]["cost_brl"] += cost_usd * usd_to_brl
        elif log.integration_type == 'serpapi':
            # SerpAPI custo é em BRL
            by_quote[quote_id]["cost_brl"] += serpapi_cost

    return by_quote


# =====================
# Endpoints
# =====================

@router.get("/months", response_model=List[MonthOption])
def get_available_months():
    """Retorna lista dos últimos 12 meses para filtro"""

    months_pt = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    month_codes = {
        1: 'jan', 2: 'fev', 3: 'mar', 4: 'abr',
        5: 'mai', 6: 'jun', 7: 'jul', 8: 'ago',
        9: 'set', 10: 'out', 11: 'nov', 12: 'dez'
    }

    result = []
    now = datetime.now()

    for i in range(12):
        date = now - timedelta(days=30 * i)
        month = date.month
        year = date.year

        value = f"{month_codes[month]}{str(year)[2:]}"
        label = f"{months_pt[month]} {year}"

        result.append(MonthOption(value=value, label=label))

    return result


@router.get("/integrations")
def get_available_integrations():
    """Retorna lista de integrações disponíveis"""
    return [
        {"value": "anthropic", "label": "Anthropic (Claude)"},
        {"value": "serpapi", "label": "SerpAPI"},
        {"value": "openai", "label": "OpenAI (GPT)"}
    ]


@router.get("/report", response_model=FinancialReportResponse)
def get_financial_report(
    period: Optional[PeriodType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    month_ref: Optional[str] = None,
    integrations: Optional[str] = None,  # Comma-separated: "anthropic,serpapi"
    project_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Gera relatório financeiro com base nos filtros.

    Retorna apenas quando filtros são aplicados.
    """

    # Parse integration list
    integration_list = None
    if integrations:
        integration_list = [i.strip() for i in integrations.split(",")]

    # Parse period
    period_start, period_end = parse_period(period, month_ref, start_date, end_date)

    # Se não há filtros, retornar vazio
    if not period_start and not period_end and not integration_list and not project_id:
        return FinancialReportResponse(
            total_usd=0,
            total_brl=0,
            totals_by_integration=[],
            transactions=[],
            period_start=None,
            period_end=None,
            usd_to_brl_rate=6.0
        )

    # Obter configuração de custos
    cost_config = get_cost_config(db)
    usd_to_brl = cost_config["usd_to_brl_rate"]

    # Construir query base
    query = db.query(IntegrationLog).join(
        QuoteRequest, IntegrationLog.quote_request_id == QuoteRequest.id
    )

    # Aplicar filtros de período
    if period_start:
        query = query.filter(IntegrationLog.created_at >= period_start)
    if period_end:
        query = query.filter(IntegrationLog.created_at <= period_end)

    # Filtrar apenas tipos válidos (excluir search_log, etc)
    valid_types = ['anthropic', 'openai', 'serpapi']
    if integration_list:
        # Filtrar pela lista fornecida (que já deve ser subset dos válidos)
        query = query.filter(IntegrationLog.integration_type.in_(integration_list))
    else:
        # Se não especificou, filtrar apenas pelos tipos válidos
        query = query.filter(IntegrationLog.integration_type.in_(valid_types))

    # Filtro de projeto
    if project_id:
        query = query.filter(QuoteRequest.project_id == project_id)

    # Ordenar por data
    query = query.order_by(IntegrationLog.created_at.desc())

    logs = query.all()

    # Agregar por cotação
    by_quote = aggregate_logs_by_quote(logs, cost_config)

    # Buscar dados das cotações (projeto, cliente, usuário)
    quote_ids = list(by_quote.keys())
    quotes_data = {}

    if quote_ids:
        quotes = db.query(
            QuoteRequest.id,
            QuoteRequest.created_at,
            QuoteRequest.pesquisador,
            Project.nome.label("project_name"),
            Client.nome.label("client_name")
        ).outerjoin(
            Project, QuoteRequest.project_id == Project.id
        ).outerjoin(
            Client, Project.client_id == Client.id
        ).filter(
            QuoteRequest.id.in_(quote_ids)
        ).all()

        for q in quotes:
            quotes_data[q.id] = {
                "created_at": q.created_at,
                "project_name": q.project_name,
                "client_name": q.client_name,
                "user_name": q.pesquisador
            }

    # Construir lista de transações
    transactions = []
    total_usd = 0.0
    total_brl = 0.0
    totals_by_api = {}

    for quote_id, data in by_quote.items():
        quote_info = quotes_data.get(quote_id, {})

        # Uma transação por API por cotação
        for api in data["apis"]:
            api_logs = [l for l in data["logs"] if l.integration_type == api]

            # Calcular custo para esta API
            if api in ('anthropic', 'openai'):
                api_cost_usd = sum(float(l.estimated_cost_usd or 0) for l in api_logs)
                api_cost_brl = api_cost_usd * usd_to_brl
            else:  # serpapi
                api_cost_usd = 0.0
                api_cost_brl = len(api_logs) * cost_config["serpapi_cost_per_call"]

            # Descrição
            description = build_transaction_description(api_logs)

            # Extrair request_data (prompt) do primeiro log que tenha
            request_data = None
            for log in api_logs:
                if log.request_data and log.request_data.get("prompt"):
                    request_data = {"prompt": log.request_data.get("prompt")}
                    break

            transactions.append(TransactionItem(
                date=quote_info.get("created_at") or api_logs[0].created_at,
                api=api,
                quote_id=quote_id,
                client_name=quote_info.get("client_name"),
                project_name=quote_info.get("project_name"),
                user_name=quote_info.get("user_name"),
                description=description,
                cost_usd=round(api_cost_usd, 6),
                cost_brl=round(api_cost_brl, 2),
                request_data=request_data
            ))

            # Acumular totais
            total_usd += api_cost_usd
            total_brl += api_cost_brl

            if api not in totals_by_api:
                totals_by_api[api] = {"usd": 0.0, "brl": 0.0, "count": 0}
            totals_by_api[api]["usd"] += api_cost_usd
            totals_by_api[api]["brl"] += api_cost_brl
            totals_by_api[api]["count"] += 1

    # Ordenar transações por data (mais recente primeiro)
    transactions.sort(key=lambda t: t.date, reverse=True)

    # Construir totais por integração
    totals_by_integration = [
        IntegrationTotal(
            api=api,
            total_usd=round(data["usd"], 6),
            total_brl=round(data["brl"], 2),
            transaction_count=data["count"]
        )
        for api, data in totals_by_api.items()
    ]

    return FinancialReportResponse(
        total_usd=round(total_usd, 6),
        total_brl=round(total_brl, 2),
        totals_by_integration=totals_by_integration,
        transactions=transactions,
        period_start=period_start,
        period_end=period_end,
        usd_to_brl_rate=usd_to_brl
    )


@router.get("/quote/{quote_id}/costs")
def get_quote_costs(quote_id: int, db: Session = Depends(get_db)):
    """
    Obter custos financeiros de uma cotação específica.
    Retorna breakdown por integração com valores em USD e BRL.
    """

    cost_config = get_cost_config(db)
    usd_to_brl = cost_config["usd_to_brl_rate"]
    serpapi_cost = cost_config["serpapi_cost_per_call"]

    # Buscar logs da cotação
    logs = db.query(IntegrationLog).filter(
        IntegrationLog.quote_request_id == quote_id
    ).all()

    # Calcular custos Anthropic
    anthropic_logs = [l for l in logs if l.integration_type == 'anthropic']
    anthropic_cost_usd = sum(float(l.estimated_cost_usd or 0) for l in anthropic_logs)
    anthropic_cost_brl = anthropic_cost_usd * usd_to_brl
    anthropic_tokens = sum(l.total_tokens or 0 for l in anthropic_logs)

    # Calcular custos OpenAI
    openai_logs = [l for l in logs if l.integration_type == 'openai']
    openai_cost_usd = sum(float(l.estimated_cost_usd or 0) for l in openai_logs)
    openai_cost_brl = openai_cost_usd * usd_to_brl
    openai_tokens = sum(l.total_tokens or 0 for l in openai_logs)

    # Calcular custos SerpAPI
    serpapi_logs = [l for l in logs if l.integration_type == 'serpapi']
    serpapi_shopping = sum(1 for l in serpapi_logs if l.api_used == 'google_shopping')
    serpapi_immersive = sum(1 for l in serpapi_logs if l.api_used == 'google_immersive_product')
    serpapi_total_calls = len(serpapi_logs)
    serpapi_cost_brl = serpapi_total_calls * serpapi_cost

    # Totais
    total_cost_usd = anthropic_cost_usd + openai_cost_usd
    total_cost_brl = anthropic_cost_brl + openai_cost_brl + serpapi_cost_brl

    return {
        "quote_id": quote_id,
        "usd_to_brl_rate": usd_to_brl,
        "anthropic": {
            "cost_usd": round(anthropic_cost_usd, 6),
            "cost_brl": round(anthropic_cost_brl, 2),
            "tokens": anthropic_tokens,
            "calls": len(anthropic_logs)
        },
        "openai": {
            "cost_usd": round(openai_cost_usd, 6),
            "cost_brl": round(openai_cost_brl, 2),
            "tokens": openai_tokens,
            "calls": len(openai_logs)
        },
        "serpapi": {
            "cost_brl": round(serpapi_cost_brl, 2),
            "cost_per_call": serpapi_cost,
            "total_calls": serpapi_total_calls,
            "shopping_calls": serpapi_shopping,
            "immersive_calls": serpapi_immersive
        },
        "total_cost_usd": round(total_cost_usd, 6),
        "total_cost_brl": round(total_cost_brl, 2)
    }


@router.get("/project/{project_id}/report", response_model=FinancialReportResponse)
def get_project_financial_report(
    project_id: int,
    period: Optional[PeriodType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    month_ref: Optional[str] = None,
    integrations: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Gera relatório financeiro específico para um projeto.
    Mesmo formato do report geral, mas filtrado por projeto.
    """
    return get_financial_report(
        period=period,
        start_date=start_date,
        end_date=end_date,
        month_ref=month_ref,
        integrations=integrations,
        project_id=project_id,
        db=db
    )
