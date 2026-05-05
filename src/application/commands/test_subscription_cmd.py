"""测试订阅命令

处理测试订阅推送的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.feed_dto import FeedDTO
from ..dto.result_dto import CommandResult
from ..dto.subscription_dto import SubscriptionDTO

if TYPE_CHECKING:
    from ...infrastructure.fetcher.rss import RSSFeedFetcher
    from ...infrastructure.fetcher.rss.parser import RSSParser


@dataclass
class TestResult:
    """测试结果"""

    feed_info: FeedDTO | None
    entry_count: int
    sample_entries: list[dict]


class TestSubscriptionCommand:
    """测试订阅命令

    处理测试订阅推送的业务用例。
    获取 Feed 并返回示例条目，不存储到数据库。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        feed_repo: FeedRepository,
        fetcher: RSSFeedFetcher,
        parser: RSSParser,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo
        self._fetcher = fetcher
        self._parser = parser

    async def execute(
        self,
        sub_id: int,
        user_id: str,
        sample_count: int = 3,
    ) -> CommandResult:
        """执行测试订阅命令

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID
            sample_count: 返回的示例条目数量

        Returns:
            CommandResult: 命令执行结果
        """
        # 1. 验证订阅存在且属于用户
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

        # 2. 获取 Feed
        feed = await self._feed_repo.get_by_id(subscription.feed_id)
        if not feed:
            return CommandResult(
                success=False,
                message=f"Feed 不存在 (ID: {subscription.feed_id})",
            )

        # 3. 抓取 Feed
        try:
            web_feed = await self._fetcher.fetch(feed.link)
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"抓取失败: {e}",
            )

        if web_feed.error:
            return CommandResult(
                success=False,
                message=f"抓取失败: {web_feed.error}",
            )

        # 4. 解析 Feed
        try:
            entries, parse_error = self._parser.parse(web_feed.content)
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"解析失败: {e}",
            )

        if parse_error:
            return CommandResult(
                success=False,
                message=f"解析失败: {parse_error}",
            )

        if not entries:
            return CommandResult(
                success=False,
                message="Feed 中没有条目",
            )

        # 5. 构建结果
        feed_dto = FeedDTO(
            id=feed.id,
            link=feed.link,
            title=feed.title or web_feed.rss_d.feed.get("title", "未知"),
            description=feed.description or web_feed.rss_d.feed.get("description", ""),
            updated_at=feed.updated_at,
        )

        # 提取示例条目
        sample_entries = []
        for entry in entries[:sample_count]:
            sample_entries.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary[:200] + "..."
                    if entry.summary and len(entry.summary) > 200
                    else entry.summary,
                    "author": entry.author,
                    "published": entry.published.isoformat()
                    if entry.published
                    else None,
                }
            )

        result = TestResult(
            feed_info=feed_dto,
            entry_count=len(entries),
            sample_entries=sample_entries,
        )

        subscription_dto = SubscriptionDTO(
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
        )

        return CommandResult(
            success=True,
            message=f"测试成功! Feed 共有 {len(entries)} 个条目",
            data={
                "subscription": subscription_dto,
                "test_result": result,
            },
        )

    async def execute_by_url(
        self,
        url: str,
        sample_count: int = 3,
    ) -> CommandResult:
        """通过 URL 测试 Feed（不需要订阅）

        Args:
            url: Feed URL
            sample_count: 返回的示例条目数量

        Returns:
            CommandResult: 命令执行结果
        """
        # 1. 抓取 Feed
        try:
            web_feed = await self._fetcher.fetch(url)
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"抓取失败: {e}",
            )

        if web_feed.error:
            return CommandResult(
                success=False,
                message=f"抓取失败: {web_feed.error}",
            )

        # 2. 解析 Feed
        try:
            entries, parse_error = self._parser.parse(web_feed.content)
        except Exception as e:
            return CommandResult(
                success=False,
                message=f"解析失败: {e}",
            )

        if parse_error:
            return CommandResult(
                success=False,
                message=f"解析失败: {parse_error}",
            )

        if not entries:
            return CommandResult(
                success=False,
                message="Feed 中没有条目",
            )

        # 3. 构建结果
        feed_dto = FeedDTO(
            id=0,  # 临时 ID
            link=url,
            title=web_feed.rss_d.feed.get("title", "未知"),
            description=web_feed.rss_d.feed.get("description", ""),
            updated_at=None,
        )

        # 提取示例条目
        sample_entries = []
        for entry in entries[:sample_count]:
            sample_entries.append(
                {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary[:200] + "..."
                    if entry.summary and len(entry.summary) > 200
                    else entry.summary,
                    "author": entry.author,
                    "published": entry.published.isoformat()
                    if entry.published
                    else None,
                }
            )

        result = TestResult(
            feed_info=feed_dto,
            entry_count=len(entries),
            sample_entries=sample_entries,
        )

        return CommandResult(
            success=True,
            message=f"测试成功! Feed 共有 {len(entries)} 个条目",
            data={"test_result": result},
        )
