from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
    FeedPollingResult,
)
from astrbot_plugin_rsshub.src.infrastructure.persistence.models import SubORM
from astrbot_plugin_rsshub.src.infrastructure.schedule.rss_scheduler import RSSScheduler


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _ExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _FakeSession:
    def __init__(self, subs: list[SubORM]):
        self._subs = subs
        self._by_id = {sub.id: sub for sub in subs}
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def execute(self, _stmt):
        return _ExecuteResult(self._subs)

    async def get(self, _model, item_id):
        return self._by_id.get(item_id)

    def add(self, _item):
        return None

    async def commit(self):
        self.commits += 1


class _FakeDatabase:
    def __init__(self, subs: list[SubORM]):
        self.subs = subs
        self.sessions: list[_FakeSession] = []

    def get_session(self):
        session = _FakeSession(self.subs)
        self.sessions.append(session)
        return session


def _sub(sub_id: int, feed_id: int, interval: int | None) -> SubORM:
    return SubORM(
        id=sub_id,
        state=1,
        user_id=f"user-{sub_id}",
        feed_id=feed_id,
        title="",
        interval=interval,
        next_check_time=None,
    )


@pytest.mark.asyncio
async def test_scheduler_groups_due_subscriptions_by_feed_and_triggers_polling(
    monkeypatch,
):
    subs = [_sub(1, 10, 5), _sub(2, 10, 15), _sub(3, 20, None)]
    fake_db = _FakeDatabase(subs)
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.schedule.rss_scheduler.get_database",
        lambda: fake_db,
    )

    polling_service = AsyncMock()
    polling_service.poll_feed_group.return_value = FeedPollingResult(
        success=True,
        status="updated",
        message="ok",
        feed_id=10,
        total_entries=2,
        new_entries=1,
    )
    dispatcher = AsyncMock()
    dispatcher.dispatch_pending_retries.return_value = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    scheduler = RSSScheduler(
        feed_polling_service=polling_service,
        notification_dispatcher=dispatcher,
        default_interval=10,
    )
    await scheduler.run_periodic_task()

    calls = polling_service.poll_feed_group.await_args_list
    assert len(calls) == 2
    assert calls[0].args == (10, [1, 2])
    assert calls[0].kwargs == {"notify_new_entries": True}
    assert calls[1].args == (20, [3])
    assert calls[1].kwargs == {"notify_new_entries": True}

    assert subs[0].next_check_time is not None
    assert subs[1].next_check_time is not None
    assert subs[2].next_check_time is not None
    assert (
        590
        <= (subs[1].next_check_time - subs[0].next_check_time).total_seconds()
        <= 610
    )
    assert (
        290
        <= (subs[2].next_check_time - subs[0].next_check_time).total_seconds()
        <= 310
    )


@pytest.mark.asyncio
async def test_scheduler_still_updates_next_check_after_polling_error(monkeypatch):
    subs = [_sub(1, 10, 5)]
    fake_db = _FakeDatabase(subs)
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.schedule.rss_scheduler.get_database",
        lambda: fake_db,
    )

    polling_service = AsyncMock()
    polling_service.poll_feed_group.side_effect = RuntimeError("boom")

    scheduler = RSSScheduler(
        feed_polling_service=polling_service,
        default_interval=10,
    )
    before = datetime.now(timezone.utc)

    await scheduler.run_periodic_task()

    polling_service.poll_feed_group.assert_awaited_once_with(
        10,
        [1],
        notify_new_entries=True,
    )
    assert subs[0].next_check_time is not None
    assert subs[0].next_check_time > before


@pytest.mark.asyncio
async def test_scheduler_does_not_poll_when_no_subscriptions_are_due(monkeypatch):
    fake_db = _FakeDatabase([])
    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.schedule.rss_scheduler.get_database",
        lambda: fake_db,
    )

    polling_service = AsyncMock()

    scheduler = RSSScheduler(
        feed_polling_service=polling_service,
        default_interval=10,
    )

    await scheduler.run_periodic_task()

    polling_service.poll_feed_group.assert_not_awaited()
