"""
订阅 Feed 命令

处理用户订阅 RSS 源的业务用例。
"""

from ...domain.entities.feed import Feed
from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...domain.value_objects.feed_url import FeedUrl
from ..dto.feed_dto import FeedDTO
from ..dto.result_dto import CommandResult
from ..dto.subscription_dto import SubscriptionDTO


class SubscribeFeedCommand:
    """
    订阅 Feed 命令

    处理用户订阅 RSS 源的业务用例。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo

    async def execute(
        self,
        url: str,
        user_id: str,
        target_session: str | None = None,
        platform_name: str | None = None,
    ) -> CommandResult:
        """
        执行订阅命令

        Args:
            url: RSS 源 URL
            user_id: 用户 ID
            target_session: 推送目标会话（可选）
            platform_name: 平台类型名（可选）

        Returns:
            CommandResult: 命令执行结果
        """
        try:
            # 1. 验证 URL 格式
            feed_url = FeedUrl(url)

            # 2. 查找或创建 Feed（领域实体）
            feed = await self._feed_repo.get_by_link(feed_url.normalized())
            if feed is None:
                feed = Feed(link=feed_url.normalized())
                feed = await self._feed_repo.save(feed)

            # 3. 检查是否已订阅
            existing = await self._subscription_repo.get_by_user_and_feed(
                user_id, feed.id
            )
            if existing:
                return CommandResult(
                    success=False,
                    message=f"已订阅该 Feed (ID: {existing.id})",
                )

            # 4. 创建订阅（领域实体）
            from ...domain.entities.subscription import Subscription

            subscription = Subscription(
                user_id=user_id,
                feed_id=feed.id,
                target_session=target_session,
                platform_name=platform_name,
            )
            subscription = await self._subscription_repo.save(subscription)

            return CommandResult(
                success=True,
                message=f"订阅成功 (ID: {subscription.id})",
                data=SubscriptionDTO(
                    id=subscription.id,
                    user_id=subscription.user_id,
                    feed_id=subscription.feed_id,
                    title=subscription.title,
                    tags=subscription.tags,
                    target_session=subscription.target_session,
                    platform_name=subscription.platform_name,
                    state=subscription.state,
                    created_at=subscription.created_at,
                    updated_at=subscription.updated_at,
                ),
            )

        except ValueError as e:
            return CommandResult(success=False, message=str(e))
