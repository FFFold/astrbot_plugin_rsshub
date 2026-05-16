"""Session-scoped push job queue.

The queue keeps push delivery serialized per target session while allowing
different sessions to send concurrently. Jobs are in-memory runtime jobs; push
history remains the durable audit log.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class PushJob:
    """Runtime state for one session push job."""

    job_id: str
    session_id: str
    description: str = ""
    status: str = "queued"
    queued_before: int = 0
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str = ""


@dataclass(frozen=True)
class PushJobResult(Generic[T]):
    """Result returned after a queued push job finishes."""

    job_id: str
    session_id: str
    ok: bool
    cancelled: bool = False
    error: str = ""
    value: T | None = None


@dataclass(frozen=True)
class StopPushJobResult:
    """Result returned by a stop request."""

    stopped: bool
    session_id: str
    job_id: str | None = None
    queued_count: int = 0
    message: str = ""


@dataclass
class _SessionQueueState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    current_job: PushJob | None = None
    current_task: asyncio.Task | None = None
    queued_count: int = 0


class SessionPushQueue:
    """Serialize push jobs per session and allow cancelling the active job."""

    def __init__(self) -> None:
        self._states: dict[str, _SessionQueueState] = {}
        self._counter = count(1)
        self._state_guard = RLock()

    def _next_job_id(self) -> str:
        return f"rss-{next(self._counter):06d}"

    def _state_for(self, session_id: str) -> _SessionQueueState:
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None:
                state = _SessionQueueState()
                self._states[session_id] = state
            return state

    def _cleanup_state_if_idle(
        self, session_id: str, state: _SessionQueueState
    ) -> None:
        """Remove per-session state when there is no active or queued work."""
        if (
            state.queued_count == 0
            and state.current_job is None
            and state.current_task is None
        ):
            self._states.pop(session_id, None)

    async def enqueue(
        self,
        session_id: str,
        work: Callable[[PushJob], Awaitable[T]],
        *,
        description: str = "",
    ) -> PushJobResult[T]:
        """Queue a push job for a session and wait for its result."""
        state = self._state_for(session_id)
        with self._state_guard:
            job = PushJob(
                job_id=self._next_job_id(),
                session_id=session_id,
                description=description,
                queued_before=state.queued_count,
            )
            state.queued_count += 1
        try:
            async with state.lock:
                with self._state_guard:
                    state.queued_count -= 1
                    job.status = "running"
                    job.started_at = datetime.now(timezone.utc)

                task = asyncio.create_task(work(job))
                with self._state_guard:
                    state.current_job = job
                    state.current_task = task
                try:
                    value = await task
                except asyncio.CancelledError:
                    job.status = "cancelled"
                    job.completed_at = datetime.now(timezone.utc)
                    return PushJobResult(
                        job_id=job.job_id,
                        session_id=session_id,
                        ok=False,
                        cancelled=True,
                        error="job cancelled",
                    )
                except Exception as ex:
                    job.status = "failed"
                    job.error = str(ex)
                    job.completed_at = datetime.now(timezone.utc)
                    return PushJobResult(
                        job_id=job.job_id,
                        session_id=session_id,
                        ok=False,
                        error=str(ex),
                    )

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                return PushJobResult(
                    job_id=job.job_id,
                    session_id=session_id,
                    ok=True,
                    value=value,
                )
        finally:
            with self._state_guard:
                if state.current_job is job:
                    state.current_job = None
                    state.current_task = None
                self._cleanup_state_if_idle(session_id, state)

    def stop_current(self, session_id: str) -> StopPushJobResult:
        """Cancel the currently running push job for a session.

        The queue is single-process and in-memory. This method uses a short
        synchronous guard because command handlers call it without awaiting.
        It may observe a just-finished task before `enqueue` has run its final
        cleanup; in that case it reports that no running job exists and lets
        the enqueue finalizer remove idle state.
        """
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None or state.current_job is None:
                if state is not None:
                    self._cleanup_state_if_idle(session_id, state)
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    message="当前会话没有正在运行的 RSS 推送任务",
                )

            job = state.current_job
            task = state.current_task
            if task is None or task.done():
                self._cleanup_state_if_idle(session_id, state)
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    queued_count=state.queued_count,
                    message="当前会话没有正在运行的 RSS 推送任务",
                )

            job.cancel_requested = True
            task.cancel()
            return StopPushJobResult(
                stopped=True,
                session_id=session_id,
                job_id=job.job_id,
                queued_count=state.queued_count,
                message=f"已请求停止 RSS 推送任务 {job.job_id}",
            )

    def get_current_job(self, session_id: str) -> PushJob | None:
        """Return the currently running job for a session, if any."""
        with self._state_guard:
            state = self._states.get(session_id)
            return state.current_job if state else None

    def get_queued_count(self, session_id: str) -> int:
        """Return the number of queued jobs for a session."""
        with self._state_guard:
            state = self._states.get(session_id)
            return state.queued_count if state else 0

    async def stop_all(self) -> None:
        """Cancel all active jobs, typically during plugin shutdown."""
        tasks = []
        with self._state_guard:
            states = list(self._states.values())
            for state in states:
                if state.current_job:
                    state.current_job.cancel_requested = True
                if state.current_task and not state.current_task.done():
                    state.current_task.cancel()
                    tasks.append(state.current_task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with self._state_guard:
            for session_id, state in list(self._states.items()):
                self._cleanup_state_if_idle(session_id, state)
