import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def set_json(key: str, value: Any, ttl: int = 3600):
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def get_json(key: str) -> Optional[Any]:
    r = await get_redis()
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None


async def delete_key(key: str):
    r = await get_redis()
    await r.delete(key)


async def publish(channel: str, message: Any):
    r = await get_redis()
    await r.publish(channel, json.dumps(message))


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
