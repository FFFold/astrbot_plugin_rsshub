"""
通知分发服务

负责将 RSS 条目分发给订阅用户。
属于应用服务，负责编排领域服务和基础设施。
"""

from ...domain.repositories.push_history_repository import PushHistoryRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository


class NotificationDispatcher:
    """
    通知分发服务

    负责将 RSS 条目分发给订阅用户。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        push_history_repo: PushHistoryRepository,
    ):
        self._subscription_repo = subscription_repo
        self._push_history_repo = push_history_repo

    async def dispatch_to_feed_subscribers(
        self,
        feed_id: int,
        content: str,
        entry_title: str,
        entry_link: str,
    ) -> None:
        """
        将条目分发给 Feed 的所有订阅者

        Args:
            feed_id: Feed ID
            content: 格式化后的消息内容
            entry_title: 条目标题
            entry_link: 条目链接
        """
        # TODO: Phase 4 实现：
        # 1. 获取 Feed 的所有启用订阅
        # 2. 为每个订阅创建推送历史记录
        # 3. 调用消息发送器发送消息
        # 4. 更新推送状态
        pass

    async def dispatch_pending_retries(self, limit: int = 100) -> None:
        """
        分发待重试的推送

        Args:
            limit: 最大处理数量
        """
        pending = await self._push_history_repo.get_pending_for_retry(limit)
        for history in pending:
            # TODO: Phase 4 实现重试逻辑
            pass
