from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub.src.application.ports import SendResult
from astrbot_plugin_rsshub.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)
from astrbot_plugin_rsshub.src.application.services.session_push_queue import (
    PushJobResult,
    SessionPushQueue,
)
from astrbot_plugin_rsshub.src.domain.entities.push_history import PushHistory
from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription


class FakeSender:
    def __init__(self, result: SendResult | None = None) -> None:
        self.result = result or SendResult(ok=True)
        self.requests = []

    async def send_to_user(self, request, context=None):
        self.requests.append((request, context))
        return self.result


class FakeSenderProvider:
    def __init__(self, sender: FakeSender) -> None:
        self.sender = sender

    def get(self, platform_name: str | None):
        return self.sender


@pytest.mark.asyncio
async def test_dispatch_sends_via_injected_sender_provider():
    sender = FakeSender()
    sub = Subscription(
        id=1,
        user_id="user-1",
        feed_id=10,
        platform_name="telegram",
        target_session="telegram:Group:1",
    )

    sub_repo = AsyncMock()
    sub_repo.get_active_by_feed_id.return_value = [sub]
    history_repo = AsyncMock()
    history_repo.get_by_sub.return_value = []
    history_repo.save.side_effect = lambda history: history

    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=FakeSenderProvider(sender),
    )

    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=10,
        content="content",
        entry_title="title",
        entry_link="https://example.com/entry",
        entry_guid="guid-1",
    )

    assert stats == {"success": 1, "failed": 0, "pending": 0}
    assert len(sender.requests) == 1
    request, context = sender.requests[0]
    assert request.session_id == "telegram:Group:1"
    assert request.message == "content"
    assert context.platform_name == "telegram"
    assert history_repo.save.await_count == 2


@pytest.mark.asyncio
async def test_dispatch_guard_skips_already_successful_entry_guid():
    sender = FakeSender()
    sub = Subscription(
        id=1,
        user_id="user-1",
        feed_id=10,
        platform_name="telegram",
        target_session="telegram:Group:1",
    )
    existing = PushHistory(
        sub_id=1,
        user_id="user-1",
        feed_id=10,
        content="old",
        entry_title="old",
        entry_link="https://example.com/entry",
        entry_guid="guid-1",
        status="success",
    )

    sub_repo = AsyncMock()
    sub_repo.get_active_by_feed_id.return_value = [sub]
    history_repo = AsyncMock()
    history_repo.get_by_sub.return_value = [existing]

    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=FakeSenderProvider(sender),
    )

    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=10,
        content="content",
        entry_title="title",
        entry_link="https://example.com/entry",
        entry_guid="guid-1",
    )

    assert stats == {"success": 0, "failed": 0, "pending": 0}
    assert sender.requests == []
    history_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_can_limit_to_selected_subscription_ids():
    sender = FakeSender()
    subs = [
        Subscription(
            id=1,
            user_id="user-1",
            feed_id=10,
            platform_name="telegram",
            target_session="telegram:Group:1",
        ),
        Subscription(
            id=2,
            user_id="user-2",
            feed_id=10,
            platform_name="telegram",
            target_session="telegram:Group:2",
        ),
    ]

    sub_repo = AsyncMock()
    sub_repo.get_active_by_feed_id.return_value = subs
    history_repo = AsyncMock()
    history_repo.get_by_sub.return_value = []
    history_repo.save.side_effect = lambda history: history

    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=FakeSenderProvider(sender),
    )

    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=10,
        content="content",
        entry_title="title",
        entry_link="https://example.com/entry",
        entry_guid="guid-1",
        subscription_ids=[2],
    )

    assert stats == {"success": 1, "failed": 0, "pending": 0}
    assert len(sender.requests) == 1
    assert sender.requests[0][0].session_id == "telegram:Group:2"


@pytest.mark.asyncio
async def test_dispatch_uses_session_queue_for_same_session():
    sender = FakeSender()
    queue = SessionPushQueue()
    subs = [
        Subscription(
            id=1,
            user_id="user-1",
            feed_id=10,
            platform_name="telegram",
            target_session="telegram:Group:1",
        ),
        Subscription(
            id=2,
            user_id="user-2",
            feed_id=10,
            platform_name="telegram",
            target_session="telegram:Group:1",
        ),
    ]

    sub_repo = AsyncMock()
    sub_repo.get_active_by_feed_id.return_value = subs
    history_repo = AsyncMock()
    history_repo.get_by_sub.return_value = []
    history_repo.save.side_effect = lambda history: history

    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=FakeSenderProvider(sender),
        push_job_queue=queue,
    )

    stats = await dispatcher.dispatch_to_feed_subscribers(
        feed_id=10,
        content="content",
        entry_title="title",
        entry_link="https://example.com/entry",
        entry_guid="guid-1",
    )

    assert stats == {"success": 2, "failed": 0, "pending": 0}
    assert len(sender.requests) == 2
    assert queue.get_current_job("telegram:Group:1") is None


@pytest.mark.asyncio
async def test_send_to_session_returns_cancelled_result_from_queue():
    sender = FakeSender()
    sub = Subscription(
        id=1,
        user_id="user-1",
        feed_id=10,
        platform_name="telegram",
        target_session="telegram:Group:1",
    )
    queue = SessionPushQueue()
    queue.enqueue = AsyncMock(
        return_value=PushJobResult(
            job_id="rss-000123",
            session_id="telegram:Group:1",
            ok=False,
            cancelled=True,
            error="job cancelled",
        )
    )

    dispatcher = NotificationDispatcher(
        subscription_repo=AsyncMock(),
        push_history_repo=AsyncMock(),
        sender_provider=FakeSenderProvider(sender),
        push_job_queue=queue,
    )

    result = await dispatcher.send_to_session(
        subscription=sub,
        content="content",
        media_urls=None,
    )

    assert result["ok"] is False
    assert result["cancelled"] is True
    assert result["job_id"] == "rss-000123"
    assert "Cancelled by /sub_stop" in result["error"]
    assert sender.requests == []


@pytest.mark.asyncio
async def test_dispatch_pending_retries_marks_cancelled_history_failed():
    sender = FakeSender()
    sub = Subscription(
        id=1,
        user_id="user-1",
        feed_id=10,
        platform_name="telegram",
        target_session="telegram:Group:1",
    )
    history = PushHistory(
        id=99,
        sub_id=1,
        user_id="user-1",
        feed_id=10,
        content="content",
        entry_title="title",
        entry_link="https://example.com/entry",
        status="retrying",
        retry_count=1,
        max_retries=3,
    )

    sub_repo = AsyncMock()
    sub_repo.get_by_id.return_value = sub
    history_repo = AsyncMock()
    history_repo.get_and_mark_retrying.return_value = [history]
    history_repo.save.side_effect = lambda value: value

    queue = SessionPushQueue()
    queue.enqueue = AsyncMock(
        return_value=PushJobResult(
            job_id="rss-000456",
            session_id="telegram:Group:1",
            ok=False,
            cancelled=True,
            error="job cancelled",
        )
    )

    dispatcher = NotificationDispatcher(
        subscription_repo=sub_repo,
        push_history_repo=history_repo,
        sender_provider=FakeSenderProvider(sender),
        push_job_queue=queue,
    )

    stats = await dispatcher.dispatch_pending_retries(limit=10)

    assert stats == {"success": 1, "failed": 0, "skipped": 0}
    assert history.status == "stopped"
    assert history.max_retries == 0
    assert "Cancelled by /sub_stop" in (history.fail_reason or "")
    history_repo.save.assert_awaited_once_with(history)
