"""测试应用命令"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSubscribeFeedCommand:
    """测试订阅 Feed 命令"""

    @pytest.mark.asyncio
    async def test_subscribe_new_feed(self):
        """测试订阅新 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import (
            SubscribeFeedCommand,
        )
        from astrbot_plugin_rsshub.src.application.settings import FeedFetchSettings
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
        from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            error=None,
            rss_d=MagicMock(feed={"title": "Test Feed"}),
        )
        fetcher.close = AsyncMock()
        fetcher_factory = MagicMock(return_value=fetcher)

        feed_repo = MagicMock()
        feed_repo.get_by_link = AsyncMock(return_value=None)
        feed_repo.save = AsyncMock(
            return_value=Feed(
                id=1, link="https://example.com/rss.xml", title="Test Feed"
            )
        )
        sub_repo = MagicMock()
        sub_repo.get_by_user_and_feed = AsyncMock(return_value=None)
        sub_repo.save = AsyncMock(
            return_value=Subscription(
                id=1,
                user_id="user123",
                feed_id=1,
                target_session="test:Group:12345",
                platform_name="telegram",
            )
        )

        cmd = SubscribeFeedCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
            fetch_settings=FeedFetchSettings(timeout=12, proxy="http://proxy.local"),
            fetcher_factory=fetcher_factory,
        )

        result = await cmd.execute(
            url="https://example.com/rss.xml",
            user_id="user123",
            target_session="test:Group:12345",
            platform_name="telegram",
        )

        assert result.success is True
        assert result.data.feed_id == 1
        assert result.data.target_session == "test:Group:12345"
        fetcher_factory.assert_called_once_with(
            timeout=12,
            proxy="http://proxy.local",
        )
        fetcher.fetch.assert_awaited_once_with("https://example.com/rss.xml")
        fetcher.close.assert_awaited_once()
        feed_repo.save.assert_awaited_once()
        sub_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_existing_feed(self):
        """测试订阅已存在的 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import (
            SubscribeFeedCommand,
        )
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
        from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription

        existing_feed = Feed(id=1, link="https://example.com/rss.xml", title="Existing")

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            error=None,
            rss_d=MagicMock(feed={"title": "Fetched Title"}),
        )
        fetcher.close = AsyncMock()
        feed_repo = MagicMock()
        feed_repo.get_by_link = AsyncMock(return_value=existing_feed)
        feed_repo.save = AsyncMock()
        sub_repo = MagicMock()
        sub_repo.get_by_user_and_feed = AsyncMock(return_value=None)
        sub_repo.save = AsyncMock(
            return_value=Subscription(id=1, user_id="user123", feed_id=1)
        )

        cmd = SubscribeFeedCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
            fetcher_factory=MagicMock(return_value=fetcher),
        )

        result = await cmd.execute(
            url="https://example.com/rss.xml",
            user_id="user123",
            target_session="test:Group:12345",
            platform_name="telegram",
        )

        assert result.success is True
        feed_repo.save.assert_not_called()
        sub_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe_invalid_url(self):
        """测试订阅无效 URL"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import (
            SubscribeFeedCommand,
        )

        feed_repo = MagicMock()
        sub_repo = MagicMock()
        fetcher_factory = MagicMock()

        cmd = SubscribeFeedCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
            fetcher_factory=fetcher_factory,
        )

        result = await cmd.execute(
            url="not-a-url",
            user_id="user123",
        )

        assert result.success is False
        assert "http" in result.message.lower()
        fetcher_factory.assert_not_called()


class TestUnsubscribeFeedCommand:
    """测试取消订阅命令"""

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self):
        """测试成功取消订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import (
            UnsubscribeFeedCommand,
        )
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
        from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription

        sub_repo = MagicMock()
        subscription = Subscription(
            id=1,
            user_id="user123",
            feed_id=1,
        )
        sub_repo.get_by_id = AsyncMock(return_value=subscription)
        sub_repo.delete = AsyncMock()

        feed_repo = MagicMock()
        feed_repo.get_by_id = AsyncMock(
            return_value=Feed(
                id=1, link="https://example.com/rss.xml", title="Test Feed"
            )
        )

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            sub_id=1,
            user_id="user123",
        )

        assert result.success is True
        assert "Test Feed" in result.message
        sub_repo.delete.assert_awaited_once_with(subscription)

    @pytest.mark.asyncio
    async def test_unsubscribe_not_found(self):
        """测试取消不存在的订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import (
            UnsubscribeFeedCommand,
        )

        sub_repo = MagicMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        feed_repo = MagicMock()

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            sub_id=999,
            user_id="user123",
        )

        assert result.success is False
        assert "不存在" in result.message

    @pytest.mark.asyncio
    async def test_unsubscribe_permission_denied(self):
        """测试无权限取消订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import (
            UnsubscribeFeedCommand,
        )
        from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription

        sub_repo = MagicMock()
        sub_repo.get_by_id = AsyncMock(
            return_value=Subscription(
                id=1,
                user_id="other_user",  # 不同用户
                feed_id=1,
                target_session="other:Group:1",
            )
        )

        feed_repo = MagicMock()

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            sub_id=1,
            user_id="user123",
            current_session="test:Group:12345",
        )

        assert result.success is False
        assert "无权限" in result.message


class TestRefreshFeedCommand:
    """测试刷新 Feed 命令"""

    @pytest.mark.asyncio
    async def test_refresh_success(self, sample_entries):
        """测试成功刷新 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import (
            RefreshFeedCommand,
        )
        from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
            FeedPollingResult,
        )
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed

        feed = Feed(
            id=1,
            link="https://example.com/rss.xml",
            title="Updated Feed",
        )
        polling_service = AsyncMock()
        polling_service.poll_feed.return_value = FeedPollingResult(
            success=True,
            status="updated",
            message="刷新完成 (ID: 1)，发现 2 个条目，新增 2 个",
            feed_id=1,
            total_entries=2,
            new_entries=2,
            feed=feed,
        )

        cmd = RefreshFeedCommand(
            MagicMock(),
            polling_service=polling_service,
        )

        result = await cmd.execute(feed_id=1)

        assert result.success is True
        assert "发现 2 个条目" in result.message
        assert result.data.title == "Updated Feed"
        polling_service.poll_feed.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_refresh_no_update(self):
        """测试 Feed 无更新"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import (
            RefreshFeedCommand,
        )
        from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
            FeedPollingResult,
        )
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed

        feed = Feed(
            id=1,
            link="https://example.com/rss.xml",
        )
        polling_service = AsyncMock()
        polling_service.poll_feed.return_value = FeedPollingResult(
            success=True,
            status="not_modified",
            message="Feed 未修改，无需更新 (ID: 1)",
            feed_id=1,
            feed=feed,
        )

        cmd = RefreshFeedCommand(
            MagicMock(),
            polling_service=polling_service,
        )

        result = await cmd.execute(feed_id=1)

        assert result.success is True
        assert "未修改" in result.message
        polling_service.poll_feed.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_refresh_fetch_error(self):
        """测试刷新时获取失败"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import (
            RefreshFeedCommand,
        )
        from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
            FeedPollingResult,
        )

        polling_service = AsyncMock()
        polling_service.poll_feed.return_value = FeedPollingResult(
            success=False,
            status="fetch_error",
            message="抓取失败: Connection timeout",
            feed_id=1,
            error="Connection timeout",
        )

        cmd = RefreshFeedCommand(
            MagicMock(),
            polling_service=polling_service,
        )

        result = await cmd.execute(feed_id=1)

        assert result.success is False
        assert "Connection timeout" in result.message
        polling_service.poll_feed.assert_awaited_once_with(1)


class TestTestSubscriptionCommand:
    """测试订阅测试命令"""

    @pytest.mark.asyncio
    async def test_test_subscription_uses_polling_service_read_path(self):
        from astrbot_plugin_rsshub.src.application.commands.test_subscription_cmd import (
            TestSubscriptionCommand,
        )
        from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
            FeedReadResult,
        )
        from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
        from astrbot_plugin_rsshub.src.domain.entities.subscription import Subscription
        from astrbot_plugin_rsshub.src.infrastructure.fetcher.rss.parser import (
            EntryParsed,
        )

        subscription = Subscription(id=5, user_id="user123", feed_id=1)
        feed = Feed(id=1, link="https://example.com/rss.xml", title="Example")
        entry = EntryParsed(
            guid="guid-1",
            title="Entry",
            link="https://example.com/entry",
            summary="Summary",
        )
        web_feed = MagicMock(rss_d=MagicMock(feed={"title": "Example"}))

        sub_repo = MagicMock()
        sub_repo.get_by_id = AsyncMock(return_value=subscription)
        feed_repo = MagicMock()
        feed_repo.get_by_id = AsyncMock(return_value=feed)
        polling_service = AsyncMock()
        polling_service.fetch_feed_entries.return_value = FeedReadResult(
            success=True,
            status="fetched",
            message="ok",
            entries=[entry],
            web_feed=web_feed,
        )

        cmd = TestSubscriptionCommand(
            subscription_repo=sub_repo,
            feed_repo=feed_repo,
            polling_service=polling_service,
        )

        result = await cmd.execute(sub_id=5, user_id="user123")

        assert result.success is True
        assert result.data["test_result"].entry_count == 1
        polling_service.fetch_feed_entries.assert_awaited_once_with(
            "https://example.com/rss.xml",
            verbose=True,
        )

    @pytest.mark.asyncio
    async def test_test_url_uses_polling_service_read_path(self):
        from astrbot_plugin_rsshub.src.application.commands.test_subscription_cmd import (
            TestSubscriptionCommand,
        )
        from astrbot_plugin_rsshub.src.application.services.feed_polling_service import (
            FeedReadResult,
        )
        from astrbot_plugin_rsshub.src.infrastructure.fetcher.rss.parser import (
            EntryParsed,
        )

        entry = EntryParsed(
            guid="guid-1",
            title="Entry",
            link="https://example.com/entry",
            summary="Summary",
        )
        web_feed = MagicMock(rss_d=MagicMock(feed={"title": "Example"}))
        polling_service = AsyncMock()
        polling_service.fetch_feed_entries.return_value = FeedReadResult(
            success=True,
            status="fetched",
            message="ok",
            entries=[entry],
            web_feed=web_feed,
        )

        cmd = TestSubscriptionCommand(
            subscription_repo=MagicMock(),
            feed_repo=MagicMock(),
            polling_service=polling_service,
        )

        result = await cmd.execute_by_url("https://example.com/rss.xml")

        assert result.success is True
        assert result.data["test_result"].feed_info.title == "Example"
        polling_service.fetch_feed_entries.assert_awaited_once_with(
            "https://example.com/rss.xml",
            verbose=True,
        )
