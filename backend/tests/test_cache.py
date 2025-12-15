"""
Testes para sistema de cache
"""
import pytest
import time
from cachetools import TTLCache
from app.utils.cache import cached_function, invalidate_cache, cache_key


def test_cache_key_generation():
    """Testa geração de chaves de cache"""
    # Mesmos argumentos = mesma chave
    key1 = cache_key(1, 2, foo="bar")
    key2 = cache_key(1, 2, foo="bar")
    assert key1 == key2

    # Argumentos diferentes = chaves diferentes
    key3 = cache_key(1, 3, foo="bar")
    assert key1 != key3


def test_cached_function_basic():
    """Testa decorator de cache básico"""
    cache = TTLCache(maxsize=10, ttl=60)
    call_count = 0

    @cached_function(cache)
    def expensive_function(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    # Primeira chamada - executa função
    result1 = expensive_function(5)
    assert result1 == 10
    assert call_count == 1

    # Segunda chamada - usa cache
    result2 = expensive_function(5)
    assert result2 == 10
    assert call_count == 1  # Não incrementou

    # Chamada com argumento diferente - executa função
    result3 = expensive_function(10)
    assert result3 == 20
    assert call_count == 2


def test_cached_function_ttl():
    """Testa expiração de cache (TTL)"""
    cache = TTLCache(maxsize=10, ttl=1)  # 1 segundo
    call_count = 0

    @cached_function(cache)
    def get_data():
        nonlocal call_count
        call_count += 1
        return "data"

    # Primeira chamada
    result1 = get_data()
    assert call_count == 1

    # Segunda chamada imediata - usa cache
    result2 = get_data()
    assert call_count == 1

    # Esperar TTL expirar
    time.sleep(1.1)

    # Terceira chamada - cache expirou, executa novamente
    result3 = get_data()
    assert call_count == 2


def test_invalidate_cache_all():
    """Testa invalidação completa do cache"""
    cache = TTLCache(maxsize=10, ttl=60)
    cache["key1"] = "value1"
    cache["key2"] = "value2"

    assert len(cache) == 2

    invalidate_cache(cache)

    assert len(cache) == 0


def test_invalidate_cache_pattern():
    """Testa invalidação por pattern"""
    cache = TTLCache(maxsize=10, ttl=60)
    cache["user_1"] = "User 1"
    cache["user_2"] = "User 2"
    cache["product_1"] = "Product 1"

    assert len(cache) == 3

    # Invalidar apenas chaves com "user"
    invalidate_cache(cache, pattern="user")

    assert len(cache) == 1
    assert "product_1" in cache


def test_cache_clear_method():
    """Testa método cache_clear do decorator"""
    cache = TTLCache(maxsize=10, ttl=60)

    @cached_function(cache)
    def get_value(x):
        return x * 2

    get_value(5)
    assert len(cache) > 0

    get_value.cache_clear()
    assert len(cache) == 0
