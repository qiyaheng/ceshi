"""极简进程内 TTL 缓存：行情数据短时间内复用，省调用额度。

Phase 1 将替换为 Redis。
"""
import copy
import time
from typing import Any, Callable

_store: dict[str, tuple[float, Any]] = {}


def ttl_get(key: str, ttl_seconds: int, factory: Callable[[], Any]) -> Any:
    now = time.time()
    hit = _store.get(key)
    if hit and now - hit[0] < ttl_seconds:
        return copy.deepcopy(hit[1])
    value = factory()
    _store[key] = (now, value)
    return value
