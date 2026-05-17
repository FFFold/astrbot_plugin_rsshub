"""
Feed 同步协调服务

负责协调 Feed 的同步任务，包括定时刷新和条目分发。
属于应用服务，负责编排领域服务。
"""

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..ports import FeedFetcherFactory, FeedParser
from ..settings import FeedFetchSettings, RSSSettings
from .feed_polling_service import FeedPollingResult, FeedPollingService


class FeedSyncService:
    """
    Feed 同步协调服务

    负责协调 Feed 的同步任务，包括定时刷新和条目分发。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
        subscription_repo: SubscriptionRepository,
        fetch_settings: FeedFetchSettings | None = None,
        rss_settings: RSSSettings | None = None,
        fetcher_factory: FeedFetcherFactory | None = None,
        parser: FeedParser | None = None,
        polling_service: FeedPollingService | None = None,
    ):
        self._polling_service = polling_service or FeedPollingService(
            feed_repo=feed_repo,
            subscription_repo=subscription_repo,
            fetch_settings=fetch_settings,
            rss_settings=rss_settings,
            fetcher_factory=fetcher_factory,
            parser=parser,
        )

    async def sync_feed(self, feed_id: int) -> FeedPollingResult:
        """
        同步单个 Feed

        获取 Feed → 抓取 RSS → 解析条目 → 去重 → 分发。

        Args:
            feed_id: Feed ID
        """
        return await self._polling_service.poll_feed(feed_id)

    async def sync_all_active_feeds(self) -> list[FeedPollingResult]:
        """同步所有启用的 Feed"""
        return await self._polling_service.poll_all_active_feeds()
