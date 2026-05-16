from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub.src.application.ports import SendResult
from astrbot_plugin_rsshub.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
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
