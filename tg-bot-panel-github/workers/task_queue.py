from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.database import async_session_factory, update_task_status
from core.logger import log
from workers.broadcaster import broadcaster


@dataclass
class BroadcastJob:
    task_id: int
    user_id: int
    text: str
    targets: list[str]
    chat_id: int
    message_id: int | None = None


class TaskQueue:
    def __init__(self, max_concurrent: int = 1):
        self._queue: asyncio.Queue[BroadcastJob] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._max_concurrent = max_concurrent
        self._running = False
        self._active_tasks: dict[int, asyncio.Task] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker_loop(i), name=f"task-worker-{i}")
            self._workers.append(worker)
        log.info("TaskQueue запущен (%d воркеров)", self._max_concurrent)

    async def stop(self) -> None:
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, job: BroadcastJob) -> None:
        await self._queue.put(job)
        log.info("Задача %d в очереди (size=%d)", job.task_id, self._queue.qsize())

    def cancel_task(self, task_id: int) -> bool:
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            broadcaster.cancel()
            return True
        return False

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._active_tasks.values() if not t.done())

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            task = asyncio.create_task(self._execute_job(job), name=f"broadcast-{job.task_id}")
            self._active_tasks[job.task_id] = task
            try:
                await task
            except asyncio.CancelledError:
                async with async_session_factory() as db:
                    await update_task_status(db, job.task_id, "cancelled")
            except Exception as e:
                log.error("Задача %d: ошибка %s", job.task_id, e)
                async with async_session_factory() as db:
                    await update_task_status(db, job.task_id, "error")
            finally:
                self._active_tasks.pop(job.task_id, None)
                self._queue.task_done()

    async def _execute_job(self, job: BroadcastJob) -> None:
        result = await broadcaster.broadcast(
            task_id=job.task_id, text=job.text, targets=job.targets, user_id=job.user_id,
        )
        log.info("Задача %d: sent=%d errors=%d", job.task_id, result["sent"], result["errors"])


task_queue = TaskQueue(max_concurrent=1)
