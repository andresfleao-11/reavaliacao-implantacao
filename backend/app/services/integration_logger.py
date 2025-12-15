"""Helper para registrar logs de integrações (Anthropic, OpenAI, SerpAPI, etc)

IMPORTANTE: Os logs de integração usam uma sessão de banco independente para garantir
que sejam persistidos mesmo em caso de erro/rollback na transação principal.
Isso é crítico para manter o histórico de consumo de APIs mesmo em cotações com erro.
"""
from sqlalchemy.orm import Session
from app.models import IntegrationLog
from app.core.database import SessionLocal
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Custos aproximados por 1M de tokens (USD) - Claude
# Fonte: https://www.anthropic.com/pricing
ANTHROPIC_COSTS = {
    "claude-sonnet-4-20250514": {
        "input": 3.00,  # $3.00 per 1M input tokens
        "output": 15.00,  # $15.00 per 1M output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
    },
}

# Custos aproximados por 1M de tokens (USD) - OpenAI
# Fonte: https://openai.com/pricing
OPENAI_COSTS = {
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
    },
    "gpt-5.2": {
        "input": 2.50,  # Estimativa baseada em gpt-4o
        "output": 10.00,
    },
}


def calculate_ai_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula o custo estimado de uma chamada de IA (Anthropic ou OpenAI)"""
    if provider == "openai":
        costs = OPENAI_COSTS.get(model, OPENAI_COSTS.get("gpt-4o", {"input": 2.50, "output": 10.00}))
    else:
        costs = ANTHROPIC_COSTS.get(model, ANTHROPIC_COSTS["claude-sonnet-4-20250514"])

    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]

    return input_cost + output_cost


def calculate_anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula o custo estimado de uma chamada Anthropic (mantido para compatibilidade)"""
    return calculate_ai_cost("anthropic", model, input_tokens, output_tokens)


def log_ai_call(
    db: Session,  # Mantido para compatibilidade, mas não usado
    quote_request_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    activity: str,
    integration_type: str = "anthropic",  # "anthropic" ou "openai"
    request_data: Optional[Dict[str, Any]] = None,
    response_summary: Optional[Dict[str, Any]] = None
):
    """
    Registra uma chamada para API de IA (Anthropic ou OpenAI).

    Usa sessão independente para garantir persistência mesmo em caso de rollback.
    """
    # Usar sessão independente para garantir que o log seja persistido
    # mesmo em caso de erro/rollback na transação principal
    log_db = SessionLocal()
    try:
        total_tokens = input_tokens + output_tokens
        estimated_cost = calculate_ai_cost(integration_type, model, input_tokens, output_tokens)

        log_entry = IntegrationLog(
            quote_request_id=quote_request_id,
            integration_type=integration_type,
            model_used=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=Decimal(str(estimated_cost)),
            activity=activity,
            request_data=request_data,
            response_summary=response_summary
        )

        log_db.add(log_entry)
        log_db.commit()

        provider_name = "OpenAI" if integration_type == "openai" else "Anthropic"
        logger.info(f"Logged {provider_name} call: {activity} - {total_tokens} tokens, ${estimated_cost:.6f}")

    except Exception as e:
        logger.error(f"Error logging AI call: {e}")
        log_db.rollback()
    finally:
        log_db.close()


def log_anthropic_call(
    db: Session,
    quote_request_id: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    activity: str,
    integration_type: str = "anthropic",  # Parâmetro adicionado para suportar OpenAI
    request_data: Optional[Dict[str, Any]] = None,
    response_summary: Optional[Dict[str, Any]] = None
):
    """
    Registra uma chamada para API de IA (mantido para compatibilidade).
    Usa log_ai_call internamente.
    """
    log_ai_call(
        db=db,
        quote_request_id=quote_request_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        activity=activity,
        integration_type=integration_type,
        request_data=request_data,
        response_summary=response_summary
    )


def log_serpapi_call(
    db: Session,  # Mantido para compatibilidade, mas não usado
    quote_request_id: int,
    api_used: str,
    search_url: str,
    activity: str,
    request_data: Optional[Dict[str, Any]] = None,
    response_summary: Optional[Dict[str, Any]] = None,
    product_link: Optional[str] = None
):
    """
    Registra uma chamada para SerpAPI.

    Usa sessão independente para garantir persistência mesmo em caso de rollback.
    """
    # Usar sessão independente para garantir que o log seja persistido
    # mesmo em caso de erro/rollback na transação principal
    log_db = SessionLocal()
    try:
        log_entry = IntegrationLog(
            quote_request_id=quote_request_id,
            integration_type="serpapi",
            api_used=api_used,
            search_url=search_url,
            product_link=product_link,
            activity=activity,
            request_data=request_data,
            response_summary=response_summary
        )

        log_db.add(log_entry)
        log_db.commit()

        logger.info(f"Logged SerpAPI call: {activity} - {api_used}")

    except Exception as e:
        logger.error(f"Error logging SerpAPI call: {e}")
        log_db.rollback()
    finally:
        log_db.close()
