"""导出订阅命令

处理用户导出订阅配置的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult


@dataclass
class ExportResult:
    """导出结果"""

    content: str
    filename: str
    count: int


class ExportSubscriptionsCommand:
    """导出订阅命令

    处理用户导出订阅配置的业务用例。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository | None = None,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo

    async def execute(
        self,
        user_id: str,
        is_admin: bool = False,
    ) -> CommandResult:
        """执行导出命令

        Args:
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)

        if not subscriptions:
            return CommandResult(
                success=False,
                message="您当前没有可导出的订阅",
            )

        if self._feed_repo is not None:
            for subscription in subscriptions:
                if getattr(subscription, "feed", None) is not None:
                    continue
                feed = await self._feed_repo.get_by_id(subscription.feed_id)
                if feed is not None:
                    subscription.feed = feed

        try:
            from ...application.services.subscription_serializer import (
                serialize_subscriptions_to_toml,
            )

            content = serialize_subscriptions_to_toml(
                user_id=user_id,
                subscriptions=subscriptions,
            )

            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rsshub_subscriptions_{user_id}_{timestamp}.toml"

            result = ExportResult(
                content=content,
                filename=filename,
                count=len(subscriptions),
            )

            return CommandResult(
                success=True,
                message=f"成功导出 {len(subscriptions)} 个订阅",
                data=result,
            )

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"导出失败: {e}",
            )
