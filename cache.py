"""Small optional Redis cache helper. The app remains usable if Redis is not configured."""
import json
import os
from typing import Any

_client = None


def _get_client():
    global _client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    if _client is None:
        try:
            import redis
            _client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
            _client.ping()
        except Exception:
            _client = False
    return _client if _client is not False else None


def get_json(key: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception:
        return None


def set_json(key: str, value: Any, ttl: int = 30) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def invalidate(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        pass
