"""
Sistema de logging estruturado em JSON
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter customizado para logs em JSON"""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # Adicionar timestamp ISO 8601
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Adicionar nível do log
        log_record['level'] = record.levelname

        # Adicionar nome do logger
        log_record['logger'] = record.name

        # Adicionar informações do processo
        log_record['process'] = {
            'id': record.process,
            'name': record.processName
        }

        # Adicionar informações da thread
        log_record['thread'] = {
            'id': record.thread,
            'name': record.threadName
        }

        # Adicionar localização do código
        log_record['location'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }


def setup_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """
    Configura o sistema de logging

    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Se True, usa formato JSON. Se False, usa formato texto.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Remover handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Criar handler para stdout
    handler = logging.StreamHandler(sys.stdout)

    if json_logs:
        # Formato JSON estruturado
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Formato texto tradicional
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Configurar níveis específicos para bibliotecas ruidosas
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: int = None,
    ip_address: str = None
):
    """
    Loga uma requisição HTTP

    Args:
        logger: Logger a ser usado
        method: Método HTTP (GET, POST, etc)
        path: Caminho da requisição
        status_code: Código de status HTTP
        duration_ms: Duração em milissegundos
        user_id: ID do usuário autenticado (opcional)
        ip_address: IP do cliente (opcional)
    """
    logger.info(
        "HTTP Request",
        extra={
            'http': {
                'method': method,
                'path': path,
                'status_code': status_code,
                'duration_ms': duration_ms
            },
            'user_id': user_id,
            'ip_address': ip_address
        }
    )


def log_database_query(
    logger: logging.Logger,
    query: str,
    params: Dict[str, Any] = None,
    duration_ms: float = None,
    rows_affected: int = None
):
    """
    Loga uma query de banco de dados

    Args:
        logger: Logger a ser usado
        query: Query SQL
        params: Parâmetros da query (opcional)
        duration_ms: Duração em milissegundos (opcional)
        rows_affected: Número de linhas afetadas (opcional)
    """
    logger.debug(
        "Database Query",
        extra={
            'database': {
                'query': query,
                'params': params,
                'duration_ms': duration_ms,
                'rows_affected': rows_affected
            }
        }
    )


def log_api_call(
    logger: logging.Logger,
    provider: str,
    endpoint: str,
    status_code: int = None,
    duration_ms: float = None,
    tokens_used: int = None,
    cost: float = None,
    error: str = None
):
    """
    Loga uma chamada a API externa

    Args:
        logger: Logger a ser usado
        provider: Provedor da API (Anthropic, SerpAPI, etc)
        endpoint: Endpoint chamado
        status_code: Código de status HTTP (opcional)
        duration_ms: Duração em milissegundos (opcional)
        tokens_used: Tokens usados (para APIs de IA) (opcional)
        cost: Custo da chamada (opcional)
        error: Mensagem de erro se houver (opcional)
    """
    level = logging.ERROR if error else logging.INFO

    logger.log(
        level,
        f"API Call to {provider}",
        extra={
            'api_call': {
                'provider': provider,
                'endpoint': endpoint,
                'status_code': status_code,
                'duration_ms': duration_ms,
                'tokens_used': tokens_used,
                'cost': cost,
                'error': error
            }
        }
    )


def log_security_event(
    logger: logging.Logger,
    event_type: str,
    user_id: int = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
    severity: str = "INFO"
):
    """
    Loga um evento de segurança

    Args:
        logger: Logger a ser usado
        event_type: Tipo do evento (login_success, login_failed, unauthorized_access, etc)
        user_id: ID do usuário (opcional)
        ip_address: IP do cliente (opcional)
        details: Detalhes adicionais (opcional)
        severity: Severidade (INFO, WARNING, ERROR, CRITICAL)
    """
    level = getattr(logging, severity.upper(), logging.INFO)

    logger.log(
        level,
        f"Security Event: {event_type}",
        extra={
            'security': {
                'event_type': event_type,
                'user_id': user_id,
                'ip_address': ip_address,
                'details': details or {}
            }
        }
    )
