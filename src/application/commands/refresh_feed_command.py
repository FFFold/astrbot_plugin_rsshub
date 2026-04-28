"""
刷新 Feed 命令

处理手动刷新 Feed 的业务用例。
"""

from ...domain.repositories.feed_repository import FeedRepository
from ..dto.feed_dto import FeedDTO
from ..dto.result_dto import CommandResult


class RefreshFeedCommand:
    """
    刷新 Feed 命令

    处理手动刷新 Feed 的业务用例。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
    ):
        self._feed_repo = feed_repo

    async def execute(self, feed_id: int) -> CommandResult:
        """
        执行刷新命令

        Args:
            feed_id: Feed ID

        Returns:
            CommandResult: 命令执行结果
        """
        feed = await self._feed_repo.get_by_id(feed_id)
        if not feed:
            return CommandResult(
                success=False,
                message=f"Feed 不存在 (ID: {feed_id})",
            )

        # TODO: Phase 4 实现 RSS 抓取和解析逻辑

        return CommandResult(
            success=True,
            message=f"刷新完成 (ID: {feed_id})",
            data=FeedDTO(
                id=feed.id,
                link=feed.link,
                title=feed.title,
                state=feed.state,
                etag=feed.etag,
                last_modified=feed.last_modified,
                created_at=feed.created_at,
                updated_at=feed.updated_at,
            ),
        )
