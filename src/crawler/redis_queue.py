import json
from typing import Optional

try:
    import redis
except Exception:  # pragma: no cover - import fallback
    redis = None

from .config import CrawlConfig


class RedisQueueClient:
    def __init__(self, config: CrawlConfig):
        if redis is None:
            raise RuntimeError(
                "The 'redis' package is required. Install it with: pip install redis"
            )

        self._client = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password or None,
            decode_responses=True,
        )
        self._client.ping()

    def push(self, queue_key: str, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False)
        self._client.rpush(queue_key, raw)

    def pop(self, queue_key: str, timeout_sec: int) -> Optional[dict]:
        item = self._client.blpop(queue_key, timeout=max(1, int(timeout_sec)))
        if item is None:
            return None

        _, raw = item
        if not raw:
            return None

        return json.loads(raw)
