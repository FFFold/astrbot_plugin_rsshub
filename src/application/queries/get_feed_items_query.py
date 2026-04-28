"""
获取 Feed 条目查询

处理获取 Feed 条目的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.feed_repository import FeedRepository
from ..dto.item_dto import ItemDTO


class FeedItemsResult(BaseModel):
    """
    Feed 条目查询结果
    """

    items: list[ItemDTO] = Field(default_factory=list, description="条目列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")

    class Config:
        frozen = True


class GetFeedItemsQuery:
    """
    获取 Feed 条目查询

    处理获取 Feed 条目的查询。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
    ):
        self._feed_repo = feed_repo

    async def execute(
        self,
        feed_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> FeedItemsResult:
        """
        执行查询

        Args:
            feed_id: Feed ID
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            FeedItemsResult: 查询结果
        """
        # TODO: Phase 4 实现 RSS 解析器，从 Feed 内容中获取条目
        # 目前返回空列表

        return FeedItemsResult(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
        )
