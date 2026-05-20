from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_rsshub.src.application.commands.export_subscriptions_cmd import (
    ExportSubscriptionsCommand,
)
from astrbot_plugin_rsshub.src.application.commands.test_subscription_cmd import (
    TestSubscriptionCommand,
)
from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import (
    UnsubscribeFeedCommand,
)
from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub.src.infrastructure.fetcher import EntryParsed


@pytest.mark.asyncio
async def test_sub_test_execute_target_dispatches_messages():
    sub_repo = MagicMock()
    feed_repo = MagicMock()
    dispatcher = MagicMock()
    dispatcher.send_to_session = AsyncMock(return_value={"ok": True})

    now = datetime.now(timezone.utc)
    entries = [
        EntryParsed(title="t1", link="l1", summary="s1", published=now),
        EntryParsed(title="t2", link="l2", summary="s2", published=now),
    ]
    polling = MagicMock()
    polling.fetch_feed_entries = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            entries=entries,
            message="ok",
            web_feed=SimpleNamespace(rss_d=SimpleNamespace(feed={"title": "timeline"})),
        )
    )

    cmd = TestSubscriptionCommand(
        subscription_repo=sub_repo,
        feed_repo=feed_repo,
        polling_service=polling,
        notification_dispatcher=dispatcher,
    )

    result = await cmd.execute_target(
        target="https://a.com/rss",
        user_id="u1",
        target_session="sess",
        platform_name="telegram",
        start=1,
        end=2,
    )
    assert result.success is True
    assert dispatcher.send_to_session.await_count == 2
    first_call = dispatcher.send_to_session.await_args_list[0].kwargs
    assert "<br" not in first_call["content"]
    assert "via l1 | timeline" in first_call["content"]


@pytest.mark.asyncio
async def test_sub_test_execute_target_preserves_video_media_item():
    sub_repo = MagicMock()
    feed_repo = MagicMock()
    dispatcher = MagicMock()
    dispatcher.send_to_session = AsyncMock(return_value={"ok": True})

    entry = EntryParsed(
        title="t1",
        link="l1",
        summary='body<video src="https://example.com/media/play?id=1"></video>',
        published=datetime.now(timezone.utc),
    )
    polling = MagicMock()
    polling.fetch_feed_entries = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            entries=[entry],
            message="ok",
            web_feed=SimpleNamespace(rss_d=SimpleNamespace(feed={"title": "timeline"})),
        )
    )

    cmd = TestSubscriptionCommand(
        subscription_repo=sub_repo,
        feed_repo=feed_repo,
        polling_service=polling,
        notification_dispatcher=dispatcher,
    )

    result = await cmd.execute_target(
        target="https://a.com/rss",
        user_id="u1",
        target_session="sess",
        platform_name="telegram",
        start=1,
        end=1,
    )

    assert result.success is True
    call = dispatcher.send_to_session.await_args.kwargs
    assert "[视频]" not in call["content"]
    assert call["media_urls"] == ["https://example.com/media/play?id=1"]
    assert call["media_items"] == [("video", "https://example.com/media/play?id=1")]


@pytest.mark.asyncio
async def test_unsubscribe_by_url_checks_and_deletes():
    sub_repo = MagicMock()
    feed_repo = MagicMock()

    feed_repo.get_by_link = AsyncMock(
        return_value=Feed(id=10, link="https://a.com/rss", title="a")
    )
    sub_repo.get_by_user = AsyncMock(
        return_value=[
            Subscription(id=1, user_id="u1", feed_id=10, target_session="sess")
        ]
    )
    sub_repo.delete = AsyncMock()

    cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)
    result = await cmd.execute_by_url(
        url="https://a.com/rss",
        user_id="u1",
        current_session="sess",
    )
    assert result.success is True
    sub_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_scope_all_non_admin_denied():
    sub_repo = MagicMock()
    feed_repo = MagicMock()
    cmd = ExportSubscriptionsCommand(sub_repo, feed_repo)
    result = await cmd.execute(user_id="u1", is_admin=False, scope="all")
    assert result.success is False
    assert "管理员" in result.message
