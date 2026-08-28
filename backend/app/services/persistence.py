"""Abstrações de persistência para evolução além do SQLite local.

O data plane atual continua usando os módulos SQLite existentes. Esta camada
permite introduzir Redis para contadores/locks e PostgreSQL para registros sem
espalhar dependência de driver pelos endpoints.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator, Protocol


class CounterStore(Protocol):
    def increment(self, key: str, *, amount: int = 1, ttl_seconds: int | None = None) -> int: ...
    def get(self, key: str) -> int: ...
    def compare_and_decrement(self, key: str, *, amount: int = 1) -> bool: ...


class SQLiteStore:
    name = "sqlite"

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    def increment(self, key: str, *, amount: int = 1, ttl_seconds: int | None = None) -> int:
        raise NotImplementedError("Use o ledger SQLite transacional existente para este backend.")

    def get(self, key: str) -> int:
        raise NotImplementedError("Use o ledger SQLite transacional existente para este backend.")

    def compare_and_decrement(self, key: str, *, amount: int = 1) -> bool:
        raise NotImplementedError("Use o ledger SQLite transacional existente para este backend.")


class RedisStore:
    name = "redis"

    def __init__(self, url: str) -> None:
        try:
            import redis  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Instale redis para ativar o backend distribuído.") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def increment(self, key: str, *, amount: int = 1, ttl_seconds: int | None = None) -> int:
        with self.client.pipeline() as pipe:
            pipe.incrby(key, amount)
            if ttl_seconds:
                pipe.expire(key, int(ttl_seconds))
            result = pipe.execute()[0]
        return int(result)

    def get(self, key: str) -> int:
        value = self.client.get(key)
        return int(value or 0)

    def compare_and_decrement(self, key: str, *, amount: int = 1) -> bool:
        script = """
        local value = tonumber(redis.call('GET', KEYS[1]) or '0')
        if value < tonumber(ARGV[1]) then return 0 end
        redis.call('DECRBY', KEYS[1], ARGV[1])
        return 1
        """
        return bool(self.client.eval(script, 1, key, int(amount)))


def configured_backend() -> str:
    value = os.environ.get("VIRAL_PERSISTENCE_BACKEND", "sqlite").strip().lower()
    return value if value in {"sqlite", "redis", "postgresql"} else "sqlite"


def backend_status() -> dict[str, Any]:
    backend = configured_backend()
    return {
        "backend": backend,
        "redis_configured": bool(os.environ.get("REDIS_URL")),
        "postgresql_configured": bool(os.environ.get("DATABASE_URL")),
        "active": "sqlite",
        "migration_ready": backend in {"sqlite", "redis", "postgresql"},
    }


def redis_store() -> RedisStore | None:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    return RedisStore(url)
