"""
取消订阅命令

处理用户取消订阅 RSS 源的业务用例。
"""

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.result_dto import CommandResult


class UnsubscribeFeedCommand:
    """
    取消订阅命令

    处理用户取消订阅 RSS 源的业务用例。
    """

    def __init__(self, subscription_repo: SubscriptionRepository):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        sub_id: int,
        user_id: str,
    ) -> CommandResult:
        """
        执行取消订阅命令

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        subscription = await self._subscription_repo.get_by_id(sub_id)
        if not subscription:
            return CommandResult(
                success=False,
                message=f"订阅不存在 (ID: {sub_id})",
            )

        if subscription.user_id != user_id:
            return CommandResult(
                success=False,
                message="无权操作此订阅",
            )

        await self._subscription_repo.delete(subscription)

        return CommandResult(
            success=True,
            message=f"已取消订阅 (ID: {sub_id})",
        )
