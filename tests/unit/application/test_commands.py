"""测试应用命令"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestSubscribeFeedCommand:
    """测试订阅 Feed 命令"""

    @pytest.mark.asyncio
    async def test_subscribe_new_feed(self, mock_event, mock_context):
        """测试订阅新 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import SubscribeFeedCommand

        # Mock 依赖
        feed_repo = MagicMock()
        feed_repo.get_by_url.return_value = None  # Feed 不存在
        feed_repo.create.return_value = MagicMock(id=1, url="https://example.com/rss.xml")

        sub_repo = MagicMock()
        sub_repo.get_by_user_and_feed.return_value = None  # 订阅不存在
        sub_repo.create.return_value = MagicMock(id=1)

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            status=200,
            content=b"<rss><channel><title>Test</title></channel></rss>",
            error=None,
        )

        parser = MagicMock()
        parser.parse.return_value = (MagicMock(title="Test Feed"), None)

        cmd = SubscribeFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(
            user_id="user123",
            platform="telegram",
            session_id="test:Group:12345",
            feed_url="https://example.com/rss.xml",
        )

        assert result.success is True
        assert result.feed_id == 1
        feed_repo.create.assert_called_once()
        sub_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_existing_feed(self, mock_event, mock_context):
        """测试订阅已存在的 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import SubscribeFeedCommand

        existing_feed = MagicMock(id=1, url="https://example.com/rss.xml")

        feed_repo = MagicMock()
        feed_repo.get_by_url.return_value = existing_feed

        sub_repo = MagicMock()
        sub_repo.get_by_user_and_feed.return_value = None
        sub_repo.create.return_value = MagicMock(id=1)

        fetcher = AsyncMock()
        parser = MagicMock()

        cmd = SubscribeFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(
            user_id="user123",
            platform="telegram",
            session_id="test:Group:12345",
            feed_url="https://example.com/rss.xml",
        )

        assert result.success is True
        # 不应该重新创建 Feed
        feed_repo.create.assert_not_called()
        sub_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_invalid_url(self):
        """测试订阅无效 URL"""
        from astrbot_plugin_rsshub.src.application.commands.subscribe_feed_cmd import (
            SubscribeFeedCommand,
            SubscribeResult,
        )

        feed_repo = MagicMock()
        sub_repo = MagicMock()
        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            status=404,
            error=MagicMock(message="Not found"),
        )
        parser = MagicMock()

        cmd = SubscribeFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(
            user_id="user123",
            platform="telegram",
            session_id="test:Group:12345",
            feed_url="https://invalid-url.com/rss.xml",
        )

        assert result.success is False
        assert result.error is not None


class TestUnsubscribeFeedCommand:
    """测试取消订阅命令"""

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self):
        """测试成功取消订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import UnsubscribeFeedCommand

        sub_repo = MagicMock()
        sub_repo.get_by_id.return_value = MagicMock(
            id=1,
            user_id="user123",
            feed_id=1,
        )
        sub_repo.delete.return_value = True

        feed_repo = MagicMock()
        feed_repo.get_subscriber_count.return_value = 0  # 无其他订阅者
        feed_repo.delete.return_value = True

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            subscription_id=1,
            user_id="user123",
        )

        assert result.success is True
        sub_repo.delete.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_unsubscribe_not_found(self):
        """测试取消不存在的订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import UnsubscribeFeedCommand

        sub_repo = MagicMock()
        sub_repo.get_by_id.return_value = None

        feed_repo = MagicMock()

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            subscription_id=999,
            user_id="user123",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unsubscribe_permission_denied(self):
        """测试无权限取消订阅"""
        from astrbot_plugin_rsshub.src.application.commands.unsubscribe_feed_cmd import UnsubscribeFeedCommand

        sub_repo = MagicMock()
        sub_repo.get_by_id.return_value = MagicMock(
            id=1,
            user_id="other_user",  # 不同用户
            feed_id=1,
        )

        feed_repo = MagicMock()

        cmd = UnsubscribeFeedCommand(sub_repo, feed_repo)

        result = await cmd.execute(
            subscription_id=1,
            user_id="user123",
        )

        assert result.success is False
        assert "permission" in result.error.lower()


class TestRefreshFeedCommand:
    """测试刷新 Feed 命令"""

    @pytest.mark.asyncio
    async def test_refresh_success(self, sample_entries):
        """测试成功刷新 Feed"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import RefreshFeedCommand

        feed = MagicMock(
            id=1,
            url="https://example.com/rss.xml",
            etag="",
            last_modified="",
        )

        feed_repo = MagicMock()
        feed_repo.get_by_id.return_value = feed

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            status=200,
            content=b"<rss>...</rss>",
            etag="new-etag",
            last_modified="new-modified",
            error=None,
        )

        parser = MagicMock()
        parser.parse.return_value = (sample_entries, None)

        sub_repo = MagicMock()
        sub_repo.get_by_feed.return_value = [
            MagicMock(user_id="user1", notify=True),
            MagicMock(user_id="user2", notify=True),
        ]

        cmd = RefreshFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(feed_id=1)

        assert result.success is True
        assert len(result.new_entries) == len(sample_entries)
        feed_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_no_update(self):
        """测试 Feed 无更新"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import RefreshFeedCommand

        feed = MagicMock(
            id=1,
            url="https://example.com/rss.xml",
        )

        feed_repo = MagicMock()
        feed_repo.get_by_id.return_value = feed

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            status=304,  # Not Modified
            error=None,
        )

        parser = MagicMock()
        sub_repo = MagicMock()

        cmd = RefreshFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(feed_id=1)

        assert result.success is True
        assert len(result.new_entries) == 0

    @pytest.mark.asyncio
    async def test_refresh_fetch_error(self):
        """测试刷新时获取失败"""
        from astrbot_plugin_rsshub.src.application.commands.refresh_feed_cmd import RefreshFeedCommand

        feed = MagicMock(id=1, url="https://example.com/rss.xml")

        feed_repo = MagicMock()
        feed_repo.get_by_id.return_value = feed

        fetcher = AsyncMock()
        fetcher.fetch.return_value = MagicMock(
            status=0,
            error=MagicMock(message="Connection timeout"),
        )

        parser = MagicMock()
        sub_repo = MagicMock()

        cmd = RefreshFeedCommand(feed_repo, sub_repo, fetcher, parser)

        result = await cmd.execute(feed_id=1)

        assert result.success is False
        assert result.error is not None
