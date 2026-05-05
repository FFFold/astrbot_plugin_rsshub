"""导出订阅命令

处理用户导出订阅配置的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult

if TYPE_CHECKING:
    from ...infrastructure.utils.subscription_io import serialize_subscriptions_to_toml


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
    ):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        user_id: str,
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
                message="没有可导出的订阅",
            )

        try:
            from ...infrastructure.utils.subscription_io import (
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
