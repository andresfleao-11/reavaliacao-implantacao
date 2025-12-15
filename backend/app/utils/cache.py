"""
Sistema de cache para configurações e dados frequentemente acessados
"""
from cachetools import TTLCache, cached
from functools import wraps
from typing import Any, Callable
import json
import hashlib


# Cache de configurações (5 minutos)
config_cache = TTLCache(maxsize=100, ttl=300)

# Cache de dados de localização (1 hora)
location_cache = TTLCache(maxsize=10, ttl=3600)

# Cache de integrações (10 minutos)
integration_cache = TTLCache(maxsize=50, ttl=600)


def cache_key(*args, **kwargs) -> str:
    """
    Gera uma chave de cache a partir dos argumentos
    """
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached_function(cache: TTLCache, key_func: Callable = None):
    """
    Decorator para cachear resultados de funções

    Args:
        cache: Cache a ser utilizado
        key_func: Função para gerar chave do cache (opcional)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gerar chave do cache
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = cache_key(*args, **kwargs)

            # Verificar se está no cache
            if key in cache:
                return cache[key]

            # Executar função e armazenar resultado
            result = func(*args, **kwargs)
            cache[key] = result
            return result

        # Adicionar método para limpar cache
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache = cache

        return wrapper
    return decorator


def invalidate_cache(cache: TTLCache, pattern: str = None):
    """
    Invalida cache baseado em pattern

    Args:
        cache: Cache a invalidar
        pattern: Pattern para buscar chaves (opcional, se None limpa tudo)
    """
    if pattern is None:
        cache.clear()
    else:
        keys_to_delete = [k for k in cache.keys() if pattern in str(k)]
        for key in keys_to_delete:
            del cache[key]
