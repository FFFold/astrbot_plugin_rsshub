"""
刷新 Feed 命令

处理手动刷新 Feed 的业务用例。
"""

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.feed_dto import FeedDTO
from ..dto.result_dto import CommandResult
from ..ports import FeedFetcherFactory
from ..settings import FeedFetchSettings


class RefreshFeedCommand:
    """
    刷新 Feed 命令

    处理手动刷新 Feed 的业务用例。
    """

    def __init__(
        self,
        feed_repo: FeedRepository,
        subscription_repo: SubscriptionRepository | None = None,
        fetch_settings: FeedFetchSettings | None = None,
        fetcher_factory: FeedFetcherFactory | None = None,
    ):
        self._feed_repo = feed_repo
        self._subscription_repo = subscription_repo
        self._fetch_settings = fetch_settings or FeedFetchSettings()
        self._fetcher_factory = fetcher_factory

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

        if self._fetcher_factory is None:
            return CommandResult(
                success=False,
                message="刷新失败: RSS 抓取器未配置",
            )

        try:
            # 实例化 RSS Feed 抓取器
            fetcher = self._fetcher_factory(
                timeout=self._fetch_settings.timeout,
                proxy=self._fetch_settings.proxy,
            )

            # 设置请求头（支持条件请求）
            headers = {}
            if feed.etag:
                headers["If-None-Match"] = feed.etag
            if feed.last_modified:
                from email.utils import format_datetime

                headers["If-Modified-Since"] = format_datetime(feed.last_modified)

            # 抓取 Feed
            try:
                result = await fetcher.fetch(feed.link, headers=headers, verbose=True)
            finally:
                await fetcher.close()

            # 检查抓取结果
            if result.error:
                return CommandResult(
                    success=False,
                    message=f"抓取失败: {result.error.error_name}",
                )

            # 检查是否未修改
            if result.status == 304:
                return CommandResult(
                    success=True,
                    message=f"Feed 未修改，无需更新 (ID: {feed_id})",
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

            # 更新 Feed 信息
            update_data = {}
            if result.rss_d:
                rss_d = result.rss_d
                if rss_d.feed.get("title"):
                    update_data["title"] = rss_d.feed.get("title")

                if result.etag:
                    update_data["etag"] = result.etag
                if result.last_modified:
                    update_data["last_modified"] = result.last_modified

            # 应用更新
            if update_data:
                for key, value in update_data.items():
                    setattr(feed, key, value)
                await self._feed_repo.save(feed)

            # 统计条目信息
            entry_count = 0
            if result.rss_d:
                entry_count = len(result.rss_d.entries)

            message = f"刷新完成 (ID: {feed_id})"
            if entry_count > 0:
                message += f"，发现 {entry_count} 个条目"

            return CommandResult(
                success=True,
                message=message,
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

        except Exception as e:
            return CommandResult(
                success=False,
                message=f"刷新失败: {str(e)}",
            )
