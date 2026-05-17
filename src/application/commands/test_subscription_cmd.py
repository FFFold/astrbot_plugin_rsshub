"""测试订阅命令

处理测试订阅推送的业务用例。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

from ...domain.repositories.feed_repository import FeedRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ..dto.feed_dto import FeedDTO
from ..dto.result_dto import CommandResult
from ..dto.subscription_dto import SubscriptionDTO
from ..ports import FeedFetcher, FeedParser
from ..services.feed_polling_service import FeedPollingService, FeedReadResult
from ..services.html_parser import HTMLParser
from ..services.notification_dispatcher import NotificationDispatcher


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
        fetcher: FeedFetcher | None = None,
        parser: FeedParser | None = None,
        polling_service: FeedPollingService | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
    ):
        self._subscription_repo = subscription_repo
        self._feed_repo = feed_repo
        self._fetcher = fetcher
        self._parser = parser
        self._polling_service = polling_service
        self._notification_dispatcher = notification_dispatcher

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

        # 3. 抓取并解析 Feed
        read_result = await self._fetch_entries(feed.link)
        if not read_result.success:
            return CommandResult(success=False, message=read_result.message)

        web_feed = read_result.web_feed
        entries = read_result.entries
        if not entries:
            return CommandResult(
                success=False,
                message="Feed 中没有条目",
            )

        # 5. 构建结果
        feed_meta = self._feed_meta(web_feed)
        feed_dto = FeedDTO(
            id=feed.id,
            link=feed.link,
            title=feed.title or feed_meta.get("title", "未知"),
            state=feed.state,
            etag=feed.etag,
            last_modified=feed.last_modified,
            created_at=feed.created_at,
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

    async def execute_target(
        self,
        target: str,
        user_id: str,
        target_session: str,
        platform_name: str,
        start: int = 1,
        end: int = 1,
    ) -> CommandResult:
        """按订阅 ID 或 URL 测试并真实推送到当前会话。"""
        if start <= 0 or end <= 0 or end < start:
            return CommandResult(success=False, message="条目范围无效，编号从 1 开始")

        if not target_session:
            return CommandResult(success=False, message="当前会话为空，无法推送")

        feed_url = ""
        feed_title = ""
        if target.isdigit():
            sub_result = await self.execute(sub_id=int(target), user_id=user_id)
            if not sub_result.success:
                return sub_result
            subscription = sub_result.data["subscription"]
            feed = await self._feed_repo.get_by_id(subscription.feed_id)
            if not feed:
                return CommandResult(success=False, message="订阅对应的 Feed 不存在")
            feed_url = feed.link
            feed_title = feed.title
        else:
            parsed = urlparse(target)
            if parsed.scheme not in {"http", "https"}:
                return CommandResult(success=False, message="目标必须是订阅 ID 或 http/https URL")
            feed_url = target

        read_result = await self._fetch_entries(feed_url)
        if not read_result.success:
            return CommandResult(success=False, message=read_result.message)

        entries = read_result.entries
        if not entries:
            return CommandResult(success=False, message="Feed 中没有条目")
        if end > len(entries):
            return CommandResult(
                success=False,
                message=f"条目范围超出上限，当前仅有 {len(entries)} 条",
            )

        selected = entries[start - 1 : end]
        if self._notification_dispatcher is None:
            return CommandResult(success=False, message="推送服务未初始化")

        fake_sub = SimpleNamespace(
            id=0,
            platform_name=platform_name,
            target_session=target_session,
        )

        pushed = 0
        for entry in selected:
            title = entry.title or ""
            summary = entry.summary or ""
            parsed = await HTMLParser(summary, feed_link=feed_url).parse()
            plain_summary = parsed.html_tree.get_plain().strip()
            content = (
                f"{title}\n\n{plain_summary}"
                if plain_summary and plain_summary != title
                else title
            )
            entry_link = getattr(entry, "link", "") or feed_url
            feed_meta = self._feed_meta(read_result.web_feed)
            feed_title = str(feed_meta.get("title", "") or "").strip() or feed_url
            author = str(getattr(entry, "author", "") or "").strip()
            via_suffix = f"via {entry_link} | {feed_title}"
            if author:
                via_suffix += f" (author: {author})"
            content = f"{content}\n\n{via_suffix}"
            media_urls = [m.url for m in parsed.media if getattr(m, "url", "")]
            media_urls.extend(
                str(enclosure.url)
                for enclosure in (getattr(entry, "enclosures", None) or [])
                if getattr(enclosure, "url", "")
            )
            media_urls = list(dict.fromkeys(media_urls))
            send_result = await self._notification_dispatcher.send_to_session(
                subscription=fake_sub,
                content=content,
                media_urls=media_urls,
                job_description=f"sub_test target={target}",
                channel_title=feed_title,
                channel_link=feed_url,
            )
            if send_result.get("ok"):
                pushed += 1

        return CommandResult(
            success=pushed > 0,
            message=f"已触发测试推送: {pushed}/{len(selected)} 条成功（范围 {start}-{end}）",
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
        # 1. 抓取并解析 Feed
        read_result = await self._fetch_entries(url)
        if not read_result.success:
            return CommandResult(success=False, message=read_result.message)

        web_feed = read_result.web_feed
        entries = read_result.entries
        if not entries:
            return CommandResult(
                success=False,
                message="Feed 中没有条目",
            )

        # 3. 构建结果
        feed_meta = self._feed_meta(web_feed)
        now = datetime.now(timezone.utc)
        feed_dto = FeedDTO(
            id=0,  # 临时 ID
            link=url,
            title=feed_meta.get("title", "未知"),
            created_at=now,
            updated_at=now,
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

    async def _fetch_entries(self, url: str) -> FeedReadResult:
        if self._polling_service is not None:
            return await self._polling_service.fetch_feed_entries(url, verbose=True)

        if self._fetcher is None or self._parser is None:
            raise RuntimeError("TestSubscriptionCommand requires feed read ports")

        try:
            web_feed = await self._fetcher.fetch(url)
        except Exception as e:
            return FeedReadResult(
                success=False,
                status="fetch_error",
                message=f"抓取失败: {e}",
                error=str(e),
            )

        if web_feed.error:
            return FeedReadResult(
                success=False,
                status="fetch_error",
                message=f"抓取失败: {web_feed.error}",
                web_feed=web_feed,
                error=str(web_feed.error),
            )

        try:
            entries, parse_error = self._parser.parse(web_feed.content)
        except Exception as e:
            return FeedReadResult(
                success=False,
                status="parse_error",
                message=f"解析失败: {e}",
                web_feed=web_feed,
                error=str(e),
            )

        if parse_error:
            return FeedReadResult(
                success=False,
                status="parse_error",
                message=f"解析失败: {parse_error}",
                web_feed=web_feed,
                error=parse_error,
            )

        return FeedReadResult(
            success=True,
            status="fetched",
            message=f"抓取完成，发现 {len(entries)} 个条目",
            entries=entries,
            web_feed=web_feed,
        )

    @staticmethod
    def _feed_meta(web_feed) -> dict:
        rss_d = getattr(web_feed, "rss_d", None)
        feed_meta = getattr(rss_d, "feed", {}) if rss_d else {}
        return feed_meta if hasattr(feed_meta, "get") else {}
