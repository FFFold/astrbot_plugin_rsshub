"""
Feed 同步协调服务

负责协调 Feed 的同步任务，包括定时刷新和条目分发。
属于应用服务，负责编排领域服务。
"""

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...infrastructure.fetcher.rss import RSSFeedFetcher
from ...infrastructure.fetcher.rss.parser import RSSParser
from ...infrastructure.utils import get_logger

logger = get_logger()


class FeedSyncService:
    """
    Feed 同步协调服务

    负责协调 Feed 的同步任务，包括定时刷新和条目分发。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
        subscription_repo: SubscriptionRepository,
    ):
        self._feed_repo = feed_repo
        self._subscription_repo = subscription_repo

    async def sync_feed(self, feed_id: int) -> None:
        """
        同步单个 Feed

        获取 Feed → 抓取 RSS → 解析条目 → 去重 → 分发。

        Args:
            feed_id: Feed ID
        """
        feed = await self._feed_repo.get_by_id(feed_id)
        if not feed:
            logger.warning("sync_feed: Feed %s 不存在", feed_id)
            return

        fetcher = RSSFeedFetcher()
        try:
            web_feed = await fetcher.fetch(feed.link)
            if web_feed.error or not web_feed.content:
                logger.warning("sync_feed: 抓取失败: feed=%s, err=%s", feed.link, web_feed.error)
                return

            parser = RSSParser()
            entries, parse_err = parser.parse(web_feed.content)
            if parse_err:
                logger.warning("sync_feed: 解析失败: feed=%s, err=%s", feed.link, parse_err)
                return

            logger.info("sync_feed: feed=%s, entries=%d", feed.link, len(entries))

            # 去重 + 记录新条目哈希
            from ...domain.services.content_filter import ContentFilterService
            filter_svc = ContentFilterService()
            new_entries = []
            for entry in entries:
                entry_guid = entry.guid or entry.link
                if entry_guid and not filter_svc.is_duplicate(feed, entry_guid):
                    new_entries.append(entry)
                    filter_svc.record_entry(feed, entry_guid)

            await self._feed_repo.save(feed)
            logger.info(
                "sync_feed: feed=%s, total=%d, new=%d",
                feed.link, len(entries), len(new_entries),
            )
        finally:
            await fetcher.close()

    async def sync_all_active_feeds(self) -> None:
        """同步所有启用的 Feed"""
        feeds = await self._feed_repo.get_all_active()
        for feed in feeds:
            if feed.id:
                await self.sync_feed(feed.id)
