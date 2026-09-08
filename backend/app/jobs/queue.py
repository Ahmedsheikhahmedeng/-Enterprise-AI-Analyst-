"""Queue abstraction and implementations (RedisJobQueue & InMemoryJobQueue)."""

import asyncio
import contextlib
import time
import uuid
from abc import ABC, abstractmethod

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.jobs.config import job_config

logger = get_logger("jobs.queue")


class JobQueue(ABC):
    """Abstract interface for background job queues."""

    @abstractmethod
    async def enqueue(self, job_id: uuid.UUID, job_type: str, priority: str = "normal") -> None:
        """Enqueue a job ID with a given priority (high, normal, low)."""
        pass

    @abstractmethod
    async def dequeue(self, worker_id: str, timeout: float = 1.0) -> uuid.UUID | None:
        """Reserve and dequeue the next available job ID with visibility timeout."""
        pass

    @abstractmethod
    async def ack(self, job_id: uuid.UUID) -> None:
        """Acknowledge successful completion and remove from in-flight tracking."""
        pass

    @abstractmethod
    async def nack(self, job_id: uuid.UUID, delay_seconds: float = 0.0) -> None:
        """Negative acknowledgement: schedule retry after delay or requeue immediately."""
        pass

    @abstractmethod
    async def requeue(self, job_id: uuid.UUID) -> None:
        """Re-insert an in-flight or interrupted job into ready queue."""
        pass

    @abstractmethod
    async def get_depth(self, priority: str | None = None) -> int:
        """Get number of pending ready jobs."""
        pass

    @abstractmethod
    async def get_all_depths(self) -> dict[str, int]:
        """Get pending depths per priority and total in-flight/delayed."""
        pass

    @abstractmethod
    async def reclaim_expired_inflight(self, visibility_timeout_seconds: float) -> list[uuid.UUID]:
        """Reclaim jobs that exceeded visibility timeout without ACK."""
        pass


class InMemoryJobQueue(JobQueue):
    """Deterministic, thread/task-safe in-memory queue for testing and standalone mode."""

    def __init__(self, visibility_timeout: float = 300.0):
        self.visibility_timeout = visibility_timeout
        self._lock = asyncio.Lock()
        self._ready: dict[str, list[uuid.UUID]] = {
            "high": [],
            "normal": [],
            "low": [],
        }
        # job_id -> (expiry_time, worker_id, priority)
        self._inflight: dict[uuid.UUID, tuple[float, str, str]] = {}
        # job_id -> (ready_time, priority)
        self._delayed: dict[uuid.UUID, tuple[float, str]] = {}

    async def enqueue(self, job_id: uuid.UUID, job_type: str, priority: str = "normal") -> None:
        p = priority.lower() if priority.lower() in self._ready else "normal"
        async with self._lock:
            self._ready[p].append(job_id)

    async def dequeue(self, worker_id: str, timeout: float = 1.0) -> uuid.UUID | None:
        start = time.monotonic()
        while True:
            async with self._lock:
                now = time.time()
                # 1. Promote due delayed jobs
                due_delayed = [
                    jid for jid, (r_time, _) in list(self._delayed.items()) if r_time <= now
                ]
                for jid in due_delayed:
                    _, prio = self._delayed.pop(jid)
                    self._ready[prio].append(jid)

                # 2. Reclaim expired in-flight jobs
                expired = [
                    jid for jid, (exp, _, prio) in list(self._inflight.items()) if exp <= now
                ]
                for jid in expired:
                    _, _, prio = self._inflight.pop(jid)
                    self._ready[prio].append(jid)

                # 3. Check queues in priority order: high -> normal -> low
                for prio in ("high", "normal", "low"):
                    if self._ready[prio]:
                        job_id = self._ready[prio].pop(0)
                        self._inflight[job_id] = (now + self.visibility_timeout, worker_id, prio)
                        return job_id

            if (time.monotonic() - start) >= timeout:
                return None
            await asyncio.sleep(0.05)

    async def ack(self, job_id: uuid.UUID) -> None:
        async with self._lock:
            self._inflight.pop(job_id, None)

    async def nack(self, job_id: uuid.UUID, delay_seconds: float = 0.0) -> None:
        async with self._lock:
            item = self._inflight.pop(job_id, None)
            prio = item[2] if item else "normal"
            if delay_seconds > 0:
                self._delayed[job_id] = (time.time() + delay_seconds, prio)
            else:
                self._ready[prio].append(job_id)

    async def requeue(self, job_id: uuid.UUID) -> None:
        async with self._lock:
            item = self._inflight.pop(job_id, None)
            prio = item[2] if item else "high"
            self._ready[prio].insert(0, job_id)

    async def get_depth(self, priority: str | None = None) -> int:
        async with self._lock:
            if priority and priority in self._ready:
                return len(self._ready[priority])
            return sum(len(q) for q in self._ready.values())

    async def get_all_depths(self) -> dict[str, int]:
        async with self._lock:
            return {
                "high": len(self._ready["high"]),
                "normal": len(self._ready["normal"]),
                "low": len(self._ready["low"]),
                "inflight": len(self._inflight),
                "delayed": len(self._delayed),
                "total_ready": sum(len(q) for q in self._ready.values()),
            }

    async def reclaim_expired_inflight(self, visibility_timeout_seconds: float) -> list[uuid.UUID]:
        reclaimed: list[uuid.UUID] = []
        now = time.time()
        async with self._lock:
            for jid, (exp, _, prio) in list(self._inflight.items()):
                if exp <= now:
                    self._inflight.pop(jid)
                    self._ready[prio].append(jid)
                    reclaimed.append(jid)
        return reclaimed


class RedisJobQueue(JobQueue):
    """Reliable Redis-backed queue with visibility timeout and priority scheduling."""

    PREFIX = "jobs:"

    def __init__(
        self, redis_client: Redis, visibility_timeout: float = job_config.VISIBILITY_TIMEOUT_SECONDS
    ):
        self.redis = redis_client
        self.visibility_timeout = visibility_timeout

    def _queue_key(self, priority: str | bytes | None) -> str:
        if isinstance(priority, bytes):
            p = priority.decode("utf-8").lower()
        elif isinstance(priority, str):
            p = priority.lower()
        else:
            p = "normal"
        p = p if p in ("high", "normal", "low") else "normal"
        return f"{self.PREFIX}ready:{p}"

    @property
    def inflight_key(self) -> str:
        return f"{self.PREFIX}inflight"

    @property
    def inflight_worker_key(self) -> str:
        return f"{self.PREFIX}inflight:workers"

    @property
    def inflight_prio_key(self) -> str:
        return f"{self.PREFIX}inflight:prios"

    @property
    def delayed_key(self) -> str:
        return f"{self.PREFIX}delayed"

    @property
    def delayed_prio_key(self) -> str:
        return f"{self.PREFIX}delayed:prios"

    async def enqueue(self, job_id: uuid.UUID, job_type: str, priority: str = "normal") -> None:
        key = self._queue_key(priority)
        await self.redis.rpush(key, str(job_id))

    async def dequeue(self, worker_id: str, timeout: float = 1.0) -> uuid.UUID | None:
        start = time.monotonic()
        while True:
            # 1. Housekeeping: promote delayed & reclaim expired inflight
            await self._promote_delayed()
            await self.reclaim_expired_inflight(self.visibility_timeout)

            now = time.time()
            # 2. Check ready queues in priority order: high -> normal -> low
            for prio in ("high", "normal", "low"):
                key = self._queue_key(prio)
                raw_id = await self.redis.lpop(key)
                if raw_id:
                    jid_str = str(raw_id)
                    # Add to in-flight with visibility deadline
                    async with self.redis.pipeline(transaction=True) as pipe:
                        pipe.zadd(self.inflight_key, {jid_str: now + self.visibility_timeout})
                        pipe.hset(self.inflight_worker_key, jid_str, worker_id)
                        pipe.hset(self.inflight_prio_key, jid_str, prio)
                        await pipe.execute()
                    try:
                        return uuid.UUID(jid_str)
                    except ValueError:
                        await self.ack(uuid.UUID(int=0))
                        continue

            if (time.monotonic() - start) >= timeout:
                return None
            await asyncio.sleep(0.05)

    async def ack(self, job_id: uuid.UUID) -> None:
        jid_str = str(job_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zrem(self.inflight_key, jid_str)
            pipe.hdel(self.inflight_worker_key, jid_str)
            pipe.hdel(self.inflight_prio_key, jid_str)
            await pipe.execute()

    async def nack(self, job_id: uuid.UUID, delay_seconds: float = 0.0) -> None:
        jid_str = str(job_id)
        prio = await self.redis.hget(self.inflight_prio_key, jid_str) or "normal"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zrem(self.inflight_key, jid_str)
            pipe.hdel(self.inflight_worker_key, jid_str)
            pipe.hdel(self.inflight_prio_key, jid_str)
            if delay_seconds > 0:
                pipe.zadd(self.delayed_key, {jid_str: time.time() + delay_seconds})
                pipe.hset(self.delayed_prio_key, jid_str, prio)
            else:
                pipe.rpush(self._queue_key(prio), jid_str)
            await pipe.execute()

    async def requeue(self, job_id: uuid.UUID) -> None:
        jid_str = str(job_id)
        prio = await self.redis.hget(self.inflight_prio_key, jid_str) or "high"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zrem(self.inflight_key, jid_str)
            pipe.hdel(self.inflight_worker_key, jid_str)
            pipe.hdel(self.inflight_prio_key, jid_str)
            pipe.lpush(self._queue_key(prio), jid_str)
            await pipe.execute()

    async def get_depth(self, priority: str | None = None) -> int:
        if priority:
            return int(await self.redis.llen(self._queue_key(priority)))
        high = await self.redis.llen(self._queue_key("high"))
        normal = await self.redis.llen(self._queue_key("normal"))
        low = await self.redis.llen(self._queue_key("low"))
        return int(high + normal + low)

    async def get_all_depths(self) -> dict[str, int]:
        high = int(await self.redis.llen(self._queue_key("high")))
        normal = int(await self.redis.llen(self._queue_key("normal")))
        low = int(await self.redis.llen(self._queue_key("low")))
        inflight = int(await self.redis.zcard(self.inflight_key))
        delayed = int(await self.redis.zcard(self.delayed_key))
        return {
            "high": high,
            "normal": normal,
            "low": low,
            "inflight": inflight,
            "delayed": delayed,
            "total_ready": high + normal + low,
        }

    async def _promote_delayed(self) -> int:
        now = time.time()
        due_items = await self.redis.zrangebyscore(self.delayed_key, 0, now)
        if not due_items:
            return 0
        promoted = 0
        for item in due_items:
            jid_str = str(item)
            prio = await self.redis.hget(self.delayed_prio_key, jid_str) or "normal"
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zrem(self.delayed_key, jid_str)
                pipe.hdel(self.delayed_prio_key, jid_str)
                pipe.rpush(self._queue_key(prio), jid_str)
                await pipe.execute()
            promoted += 1
        return promoted

    async def reclaim_expired_inflight(self, visibility_timeout_seconds: float) -> list[uuid.UUID]:
        now = time.time()
        expired_items = await self.redis.zrangebyscore(self.inflight_key, 0, now)
        if not expired_items:
            return []
        reclaimed: list[uuid.UUID] = []
        for item in expired_items:
            jid_str = str(item)
            prio = await self.redis.hget(self.inflight_prio_key, jid_str) or "normal"
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zrem(self.inflight_key, jid_str)
                pipe.hdel(self.inflight_worker_key, jid_str)
                pipe.hdel(self.inflight_prio_key, jid_str)
                pipe.rpush(self._queue_key(prio), jid_str)
                await pipe.execute()
            with contextlib.suppress(ValueError):
                reclaimed.append(uuid.UUID(jid_str))
        return reclaimed
