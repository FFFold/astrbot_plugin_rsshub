"""
Feed 同步协调服务

负责协调 Feed 的同步任务，包括定时刷新和条目分发。
属于应用服务，负责编排领域服务。
"""

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository


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

        Args:
            feed_id: Feed ID
        """
        # TODO: Phase 4 实现：
        # 1. 获取 Feed 实体
        # 2. 抓取 RSS 内容
        # 3. 解析条目
        # 4. 使用 ContentFilterService 去重
        # 5. 将新条目分发到消息推送队列
        pass

    async def sync_all_active_feeds(self) -> None:
        """同步所有启用的 Feed"""
        feeds = await self._feed_repo.get_all_active()
        for feed in feeds:
            if feed.id:
                await self.sync_feed(feed.id)
