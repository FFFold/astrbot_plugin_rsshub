"""
搜索 Feed 查询

处理搜索 Feed 的查询。
"""

from pydantic import BaseModel, Field

from ...domain.repositories.feed_repository import FeedRepository
from ..dto.feed_dto import FeedDTO


class SearchFeedsResult(BaseModel):
    """
    搜索 Feed 查询结果
    """

    feeds: list[FeedDTO] = Field(default_factory=list, description="Feed 列表")
    total: int = Field(default=0, description="总数")
    query: str = Field(default="", description="搜索关键词")

    class Config:
        frozen = True


class SearchFeedsQuery:
    """
    搜索 Feed 查询

    处理搜索 Feed 的查询。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
    ):
        self._feed_repo = feed_repo

    async def execute(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchFeedsResult:
        """
        执行搜索

        Args:
            query: 搜索关键词
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            SearchFeedsResult: 查询结果
        """
        # TODO: Phase 4 实现 Feed 搜索逻辑
        # 目前返回空列表

        return SearchFeedsResult(
            feeds=[],
            total=0,
            query=query,
        )
