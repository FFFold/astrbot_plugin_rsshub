"""
获取订阅列表查询

处理获取用户订阅列表的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.subscription_dto import SubscriptionDTO


class SubscriptionsResult(BaseModel):
    """
    订阅列表查询结果
    """

    subscriptions: list[SubscriptionDTO] = Field(
        default_factory=list, description="订阅列表"
    )
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")

    class Config:
        frozen = True


class GetSubscriptionsQuery:
    """
    获取订阅列表查询

    处理获取用户订阅列表的查询。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
    ):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> SubscriptionsResult:
        """
        执行查询

        Args:
            user_id: 用户 ID
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            SubscriptionsResult: 查询结果
        """
        subscriptions = await self._subscription_repo.get_by_user(user_id)

        sub_dtos = [
            SubscriptionDTO(
                id=sub.id,
                user_id=sub.user_id,
                feed_id=sub.feed_id,
                title=sub.title,
                tags=sub.tags,
                target_session=sub.target_session,
                platform_name=sub.platform_name,
                state=sub.state,
                created_at=sub.created_at,
                updated_at=sub.updated_at,
            )
            for sub in subscriptions
        ]

        return SubscriptionsResult(
            subscriptions=sub_dtos,
            total=len(sub_dtos),
            page=page,
            page_size=page_size,
        )
