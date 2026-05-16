from __future__ import annotations

import asyncio

import pytest
from astrbot_plugin_rsshub.src.application.services.session_push_queue import (
    SessionPushQueue,
)


@pytest.mark.asyncio
async def test_same_session_jobs_run_serially():
    queue = SessionPushQueue()
    events: list[str] = []
    release_first = asyncio.Event()

    async def first(job):
        events.append(f"start:{job.job_id}")
        await release_first.wait()
        events.append(f"end:{job.job_id}")
        return "first"

    async def second(job):
        events.append(f"start:{job.job_id}")
        events.append(f"end:{job.job_id}")
        return "second"

    first_task = asyncio.create_task(queue.enqueue("session-1", first))
    await asyncio.sleep(0)
    second_task = asyncio.create_task(queue.enqueue("session-1", second))
    await asyncio.sleep(0)

    assert queue.get_queued_count("session-1") == 1
    assert events == ["start:rss-000001"]

    release_first.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert first_result.ok is True
    assert first_result.value == "first"
    assert second_result.ok is True
    assert second_result.value == "second"
    assert events == [
        "start:rss-000001",
        "end:rss-000001",
        "start:rss-000002",
        "end:rss-000002",
    ]


@pytest.mark.asyncio
async def test_different_sessions_can_run_concurrently():
    queue = SessionPushQueue()
    both_started = asyncio.Event()
    started: set[str] = set()

    async def work(job):
        started.add(job.session_id)
        if started == {"session-1", "session-2"}:
            both_started.set()
        await both_started.wait()
        return job.session_id

    results = await asyncio.gather(
        queue.enqueue("session-1", work),
        queue.enqueue("session-2", work),
    )

    assert {result.value for result in results} == {"session-1", "session-2"}


@pytest.mark.asyncio
async def test_stop_current_cancels_running_job_and_releases_next_job():
    queue = SessionPushQueue()
    started = asyncio.Event()
    next_ran = asyncio.Event()

    async def long_running(_job):
        started.set()
        await asyncio.sleep(60)
        return "never"

    async def next_job(_job):
        next_ran.set()
        return "next"

    first_task = asyncio.create_task(queue.enqueue("session-1", long_running))
    await started.wait()
    second_task = asyncio.create_task(queue.enqueue("session-1", next_job))
    await asyncio.sleep(0)

    stop_result = queue.stop_current("session-1")

    assert stop_result.stopped is True
    assert stop_result.job_id == "rss-000001"
    assert stop_result.queued_count == 1

    first_result = await first_task
    second_result = await second_task

    assert first_result.cancelled is True
    assert second_result.ok is True
    assert second_result.value == "next"
    assert next_ran.is_set()
