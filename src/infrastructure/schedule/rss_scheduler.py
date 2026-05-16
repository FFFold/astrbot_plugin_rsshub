"""RSS 调度器模块

负责定时检查订阅的 RSS 源并触发更新推送。
基于订阅维度调度，实现会话/订阅级 interval 生效。
"""

from __future__ import annotations

import asyncio
import hashlib
import zlib
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from itertools import chain
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

import aiohttp
from sqlmodel import or_, select

from ...application.ports import MessageSenderProvider
from ...application.services.notification_dispatcher import NotificationDispatcher
from ..fetcher.rss import RSSFeedFetcher
from ..messaging.senders.provider import InfrastructureMessageSenderProvider
from ..persistence.database import get_database
from ..persistence.models import FeedORM, SubORM
from ..persistence.push_history_repository_impl import get_push_history_repository
from ..persistence.subscription_repository_impl import get_subscription_repository
from ..utils import get_logger
from ..utils.lock import locked
from ..utils.normalizer import normalize_identifier, normalize_text

if TYPE_CHECKING:
    from ...domain.entities.feed import Feed
    from ...domain.entities.subscription import Subscription
    from ...domain.repositories.push_history_repository import PushHistoryRepository
    from ...domain.repositories.subscription_repository import SubscriptionRepository

logger = get_logger()


class NotificationService(Protocol):
    """通知服务协议（由应用层实现）"""

    async def notify_feed_update(
        self,
        feed: Feed,
        subscriptions: list[Subscription],
        entries: list[dict[str, Any]],
    ) -> bool:
        """通知订阅者 Feed 更新

        Args:
            feed: 更新的 Feed
            subscriptions: 相关订阅列表
            entries: 新条目列表

        Returns:
            是否成功
        """
        ...

    async def notify_feed_error(
        self,
        feed: Feed,
        subscriptions: list[Subscription],
        error: str,
    ) -> None:
        """通知订阅者 Feed 错误

        Args:
            feed: 出错的 Feed
            subscriptions: 相关订阅列表
            error: 错误描述
        """
        ...


class SchedulerStats:
    """调度器统计"""

    def __init__(self) -> None:
        self.cached_count = 0
        self.updated_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.not_updated_count = 0
        self.empty_count = 0

    def cached(self) -> None:
        self.cached_count += 1

    def updated(self) -> None:
        self.updated_count += 1

    def failed(self) -> None:
        self.failed_count += 1

    def skipped(self) -> None:
        self.skipped_count += 1

    def not_updated(self) -> None:
        self.not_updated_count += 1

    def empty(self) -> None:
        self.empty_count += 1

    def print_summary(self) -> None:
        if self.cached_count + self.updated_count + self.failed_count > 0:
            logger.debug(
                "RSS调度统计: 更新=%s, 缓存=%s, 失败=%s, 跳过=%s",
                self.updated_count,
                self.cached_count,
                self.failed_count,
                self.skipped_count,
            )

    def reset(self) -> None:
        self.cached_count = 0
        self.updated_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.not_updated_count = 0
        self.empty_count = 0


class RSSScheduler:
    """RSS 调度器，负责定时检查订阅源并触发推送"""

    TIMEOUT: Final = 300
    HASH_HISTORY_MIN: Final = 200
    HASH_HISTORY_MULTIPLIER: Final = 2
    HASH_HISTORY_HARD_LIMIT: Final = 5000
    HASH_HISTORY_ABSOLUTE_MAX: Final = 20000
    TRACKING_QUERY_PARAMS: Final = frozenset(
        {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "utm_id",
            "gclid",
            "fbclid",
            "mc_cid",
            "mc_eid",
            "spm",
            "ref",
            "ref_src",
        }
    )

    def __init__(
        self,
        fetcher: RSSFeedFetcher | None = None,
        notification_service: NotificationService | None = None,
        hash_history_min: int = 200,
        hash_history_multiplier: int = 2,
        hash_history_hard_limit: int = 5000,
        bootstrap_skip_history: bool = True,
        history_entry_limit: int = 0,
        default_interval: int = 10,
        history_retention_days: int = 30,
        sender_provider: MessageSenderProvider | None = None,
    ) -> None:
        self._fetcher = fetcher or RSSFeedFetcher()
        self._notification_service = notification_service
        self._stats = SchedulerStats()
        self._running = False
        self._bg_task: asyncio.Task | None = None
        self._hash_history_min = max(1, hash_history_min)
        self._hash_history_multiplier = max(1, hash_history_multiplier)
        self._hash_history_hard_limit = max(
            self._hash_history_min, hash_history_hard_limit
        )
        self._bootstrap_skip_history = bootstrap_skip_history
        self._history_entry_limit = max(0, history_entry_limit)
        self._default_interval = max(1, default_interval)
        self._history_retention_days = max(1, history_retention_days)
        self._sender_provider = sender_provider or InfrastructureMessageSenderProvider()

        # 初始化 NotificationDispatcher 用于重试机制
        self._notification_dispatcher = NotificationDispatcher(
            subscription_repo=cast(
                "SubscriptionRepository", get_subscription_repository()
            ),
            push_history_repo=cast(
                "PushHistoryRepository", get_push_history_repository()
            ),
            sender_provider=self._sender_provider,
        )

    async def start(self) -> None:
        """启动调度器"""
        self._running = True
        logger.info("RSS调度器已启动")

    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
        await self._fetcher.close()
        logger.info("RSS调度器已停止")

    async def run_periodic_task(self) -> None:
        """执行一次定时任务（每分钟调用）"""
        self._stats.print_summary()
        self._stats.reset()

        now = datetime.now(timezone.utc)
        if now.minute == 0:
            await self._cleanup_old_records()

        # 处理待重试的推送（每分钟都执行）
        try:
            retry_stats = await self._notification_dispatcher.dispatch_pending_retries(
                limit=50
            )
            if retry_stats.get("success", 0) > 0 or retry_stats.get("failed", 0) > 0:
                logger.info(
                    "重试推送完成: 成功=%s, 失败=%s, 跳过=%s",
                    retry_stats.get("success", 0),
                    retry_stats.get("failed", 0),
                    retry_stats.get("skipped", 0),
                )
        except Exception as e:
            logger.error("处理重试推送失败: %s", e, exc_info=True)

        try:
            db = get_database()
            async with db.get_session() as session:
                stmt = (
                    select(SubORM)
                    .join(FeedORM)
                    .where(
                        SubORM.state == 1,
                        FeedORM.state == 1,
                        or_(
                            cast(Any, SubORM.next_check_time).is_(None),
                            SubORM.next_check_time <= now,
                        ),
                    )
                )
                result = await session.execute(stmt)
                due_subs = list(result.scalars().all())

                if not due_subs:
                    return

                # 按 (feed_id, interval) 分组
                groups: dict[tuple[int, int], list[SubORM]] = {}
                for sub in due_subs:
                    if sub.feed_id is None:
                        continue
                    effective_interval = self._resolve_interval(sub)
                    key = (sub.feed_id, effective_interval)
                    groups.setdefault(key, []).append(sub)

                for (feed_id, interval), subs in groups.items():
                    feed_orm = await session.get(FeedORM, feed_id)  # type: ignore[arg-type]
                    if not feed_orm:
                        continue
                    await self._process_feed_group(session, feed_orm, subs, interval)

        except Exception as ex:
            logger.error("执行定时任务失败: %s", ex, exc_info=True)

    async def _cleanup_old_records(self) -> None:
        """清理指定天数前的推送历史记录"""
        try:
            deleted_count = await self._notification_dispatcher.cleanup_old_records(
                days=self._history_retention_days
            )
            if deleted_count > 0:
                logger.info(
                    "清理了 %s 条超过 %s 天的推送历史记录",
                    deleted_count,
                    self._history_retention_days,
                )
        except Exception as e:
            logger.error("清理推送历史记录失败: %s", e, exc_info=True)

    def _resolve_interval(self, sub: SubORM) -> int:
        """解析订阅生效的监控间隔"""
        if sub.interval and sub.interval > 0:
            return sub.interval
        return self._default_interval

    async def _process_feed_group(
        self,
        session,
        feed: FeedORM,
        subs: list[SubORM],
        interval: int,
    ) -> None:
        """处理一个 Feed 组"""
        if feed.id is None:
            return
        await self._do_monitor_feed(session, feed, subs, interval)

    @locked("#feed.id")
    async def _do_monitor_feed(
        self,
        session,
        feed: FeedORM,
        subs: list[SubORM],
        interval: int,
    ) -> None:
        """实际监控 Feed（已加锁）"""
        headers = {
            "If-Modified-Since": format_datetime(feed.last_modified or feed.updated_at)
        }
        if feed.etag:
            headers["If-None-Match"] = feed.etag

        wf = await self._fetcher.fetch(
            feed.link,
            headers=headers,
            verbose=False,
        )
        rss_d = wf.rss_d

        feed_updated_fields: set[str] = set()
        schedule_action: tuple[str, str | None] = ("success", None)

        try:
            if wf.status == 304:
                self._stats.cached()

            elif rss_d is None:
                schedule_action = (
                    "error",
                    wf.error.error_name if wf.error else "未知错误",
                )
                if self._all_subs_blocked(subs):
                    feed.state = 0
                    feed_updated_fields.add("state")
                self._stats.failed()

            elif not rss_d.entries:
                schedule_action = ("success", None)
                self._stats.empty()

            else:
                etag = wf.etag
                if etag and etag != feed.etag:
                    feed.etag = etag
                    feed_updated_fields.add("etag")
                    logger.debug("Updated ETag for feed %s: %s", feed.id, etag)

                title = rss_d.feed.get("title", "")
                if title and title != feed.title:
                    feed.title = title[:1024]
                    feed_updated_fields.add("title")

                old_groups = self._migrate_hashes(feed.entry_hashes or [])
                fetched_entries = len(rss_d.entries)
                new_groups, updated_entries = self._calculate_update(
                    old_groups,
                    rss_d.entries,
                    feed_link=feed.link,
                )
                merged = self._merge_hash_history(
                    old_groups, new_groups, fetched_entries
                )

                if not old_groups:
                    # 首次初始化
                    feed.last_modified = wf.last_modified
                    feed.entry_hashes = merged
                    feed_updated_fields.update({"last_modified", "entry_hashes"})

                    if not updated_entries:
                        self._stats.not_updated()
                    elif self._bootstrap_skip_history:
                        logger.info(
                            "Feed首次初始化跳过历史: %s, entries=%s",
                            feed.link,
                            len(updated_entries),
                        )
                        self._stats.not_updated()
                    else:
                        await self._send_notifications(feed, subs, updated_entries)
                        feed.last_modified = wf.last_modified
                        feed.entry_hashes = merged
                        feed_updated_fields.update({"last_modified", "entry_hashes"})
                        self._stats.updated()

                elif not updated_entries:
                    if merged != old_groups:
                        feed.entry_hashes = merged
                        feed_updated_fields.add("entry_hashes")
                    self._stats.not_updated()

                else:
                    await self._send_notifications(feed, subs, updated_entries)
                    feed.last_modified = wf.last_modified
                    feed.entry_hashes = merged
                    feed_updated_fields.update({"last_modified", "entry_hashes"})
                    self._stats.updated()

        finally:
            if feed_updated_fields:
                session.add(feed)
                await session.commit()
                logger.debug("Feed %s 已更新字段: %s", feed.id, feed_updated_fields)

        action, reason = schedule_action
        if action == "success":
            await self._schedule_after_success(subs, interval)
        elif action == "error" and reason:
            await self._schedule_after_error(subs, interval)

    async def _send_notifications(
        self,
        feed: FeedORM,
        subs: list[SubORM],
        entries: list[dict],
    ) -> None:
        """发送通知"""
        if not self._notification_service:
            return

        # 按时间排序（新到旧）
        sorted_entries = sorted(
            entries,
            key=lambda e: e.get("published_parsed") or e.get("updated_parsed") or (),
            reverse=True,
        )

        # 应用历史条目限制
        if self._history_entry_limit > 0:
            sorted_entries = sorted_entries[: self._history_entry_limit]

        # 转换为 EntryParsed 对象
        from ..domain.entities.feed import Feed
        from ..domain.entities.subscription import Subscription

        feed_entity = Feed(
            id=feed.id,
            state=feed.state,
            link=feed.link,
            title=feed.title,
        )
        subscription_entities = [
            Subscription(
                id=sub.id,
                state=sub.state,
                user_id=sub.user_id,
                feed_id=sub.feed_id,
                title=sub.title or "",
                target_session=sub.target_session,
                platform_name=sub.platform_name,
                interval=sub.interval,
            )
            for sub in subs
        ]

        await self._notification_service.notify_feed_update(
            feed_entity, subscription_entities, sorted_entries
        )

    async def _update_next_check_times(self, subs: list[SubORM], interval: int) -> None:
        """更新订阅的下次检查时间"""
        now = datetime.now(timezone.utc)
        db = get_database()
        async with db.get_session() as session:
            for sub in subs:
                if sub.id is None:
                    continue
                db_sub = await session.get(SubORM, sub.id)
                if db_sub:
                    db_sub.next_check_time = now + timedelta(minutes=interval)
                    session.add(db_sub)
            await session.commit()

    async def _schedule_after_success(self, subs: list[SubORM], interval: int) -> None:
        """成功后更新下次检查时间"""
        await self._update_next_check_times(subs, interval)

    async def _schedule_after_error(self, subs: list[SubORM], interval: int) -> None:
        """失败后更新下次检查时间"""
        await self._update_next_check_times(subs, interval)

    @staticmethod
    def _all_subs_blocked(subs: list[SubORM]) -> bool:
        """检查是否所有订阅都被禁用"""
        return len(subs) > 0 and all((s.state == 0) for s in subs)

    def _migrate_hashes(self, raw: list) -> list[list[str]]:
        """将旧格式哈希列表迁移为新格式"""
        if not raw:
            return []
        if isinstance(raw[0], list):
            return raw
        groups: list[list[str]] = []
        current: list[str] = []
        for h in raw:
            if h.startswith("sid:") and current:
                groups.append(current)
                current = []
            current.append(h)
        if current:
            groups.append(current)
        return groups

    async def _calculate_update(
        self,
        old_groups: list[list[str]],
        entries: list,
        feed_link: str | None = None,
    ) -> tuple[list[list[str]], list]:
        """计算哪些条目是新的"""
        old_flat = {h for group in old_groups for h in group if h}
        known_hashes = set(old_flat)
        new_groups: list[list[str]] = []
        updated_entries = []

        for entry in entries:
            entry_hashes = await self._hash_entry(entry, feed_link)
            stable_hash = next((h for h in entry_hashes if h.startswith("sid:")), "")

            known_by_identity = bool(stable_hash) and stable_hash in known_hashes
            known_by_compat = False
            if not known_by_identity and not stable_hash:
                known_by_compat = any(h in known_hashes for h in entry_hashes)

            if not (known_by_identity or known_by_compat):
                updated_entries.append(entry)

            new_groups.append(entry_hashes)
            if stable_hash:
                known_hashes.add(stable_hash)

        return new_groups, updated_entries

    async def _hash_entry(self, entry: dict, feed_link: str | None = None) -> list[str]:
        """计算条目的去重指纹（含文本和媒体内容）"""
        upstream_material = self._upstream_material(entry)
        upstream_crc = (
            hex(zlib.crc32(upstream_material.encode("utf-8", errors="ignore")))[2:]
            if upstream_material
            else ""
        )

        entry_id = normalize_identifier(str(entry.get("id") or entry.get("guid") or ""))
        link = self._resolve_entry_link(entry, feed_link)
        title = normalize_text(str(entry.get("title") or ""))
        summary = normalize_text(
            str(entry.get("summary") or entry.get("description") or ""),
            max_length=2048,
        )

        stable_material = ""
        if entry_id:
            stable_material = f"v3|id={entry_id}"
        elif link:
            stable_material = f"v3|link={link}"
        elif title:
            stable_material = f"v3|title={title}"
        elif summary:
            stable_material = f"v3|summary={summary[:256]}"

        content_material = f"v3|title={title}|link={link}|summary={summary[:512]}"

        fingerprints: list[str] = []
        if stable_material:
            stable_hash = f"sid:{hashlib.sha256(stable_material.encode()).hexdigest()}"
            fingerprints.append(stable_hash)

        content_hash = hashlib.sha256(content_material.encode()).hexdigest()
        if content_hash not in fingerprints:
            fingerprints.append(content_hash)

        if upstream_crc and upstream_crc not in fingerprints:
            fingerprints.append(upstream_crc)

        legacy_hash = self._legacy_crc32(entry)
        if legacy_hash and legacy_hash not in fingerprints:
            fingerprints.append(legacy_hash)

        # 媒体内容指纹：下载 enclosure 并计算 SHA256
        media_hashes = await self._media_content_hashes(entry)
        for mh in media_hashes:
            if mh not in fingerprints:
                fingerprints.append(mh)

        return fingerprints

    async def _media_content_hashes(self, entry: dict) -> list[str]:
        """下载 entry 的媒体内容并计算 SHA256 指纹"""
        enclosures = entry.get("enclosures") or []
        if not enclosures:
            media_list = entry.get("media_content") or []
            enclosures = [m for m in media_list if isinstance(m, dict)]

        hashes: list[str] = []
        for enc in enclosures[:3]:  # 最多取 3 个
            url = str(enc.get("url") or enc.get("href") or "")
            if not url or not url.startswith("http"):
                continue
            mime = str(enc.get("type") or "")
            # 只处理图片和视频
            if not (mime.startswith("image/") or mime.startswith("video/")):
                continue
            try:
                sha256 = await self._fetch_media_sha256(url)
                if sha256:
                    hashes.append(f"media:{sha256}")
            except Exception:
                pass  # 单个媒体下载失败不影响整体
        return hashes

    async def _fetch_media_sha256(self, url: str) -> str | None:
        """下载媒体（限 5MB）并返回 SHA256，不阻塞整个流程"""
        try:
            session_lock = self._fetcher._session_lock
            if session_lock is None:
                return None
            async with session_lock:
                session = self._fetcher._session
                if session is None or session.closed:
                    return None
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                chunk_size = 8192
                limit = 5 * 1024 * 1024  # 5MB
                sha = hashlib.sha256()
                async for chunk in resp.content.iter_chunked(chunk_size):
                    sha.update(chunk)
                    if resp.content.total_bytes and resp.content.total_bytes > limit:
                        return None  # 文件太大，忽略
                    if sha.digest_size > limit:  # 简单大小保护
                        return None
                return sha.hexdigest()
        except Exception:
            return None

    @staticmethod
    def _upstream_material(entry: dict) -> str:
        """构建上游兼容的身份材料"""
        guid = str(entry.get("guid") or "").strip()
        link = str(entry.get("link") or "").strip()
        title = str(entry.get("title") or "").strip()
        summary = str(entry.get("summary") or "").strip()

        content_items = entry.get("content") or []
        first_content_value = ""
        if isinstance(content_items, list):
            for content in content_items:
                if isinstance(content, dict):
                    value = content.get("value")
                    if value:
                        first_content_value = str(value).strip()
                        break

        return "\n".join([guid, link, title, summary, first_content_value])

    @staticmethod
    def _resolve_entry_link(entry: dict, feed_link: str | None = None) -> str:
        """解析条目链接（清理追踪参数）"""
        link = str(entry.get("link") or entry.get("guid") or "").strip()
        if not link:
            return ""
        if feed_link and not link.startswith("http"):
            from urllib.parse import urljoin

            link = urljoin(feed_link, link)

        # 清理追踪参数
        try:
            from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

            parsed = urlparse(link)
            if parsed.query:
                # 过滤掉追踪参数
                filtered_params = [
                    (k, v)
                    for k, v in parse_qsl(parsed.query)
                    if k not in RSSScheduler.TRACKING_QUERY_PARAMS
                ]
                # 重建URL
                link = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        urlencode(filtered_params),
                        parsed.fragment,
                    )
                )
        except Exception:
            pass  # 清理失败时保持原链接

        return link

    @staticmethod
    def _legacy_crc32(entry: dict) -> str:
        """遗留 v1 指纹（向后兼容）"""
        hash_base = (
            str(entry.get("link", ""))
            + str(entry.get("title", ""))
            + str(entry.get("published", ""))
        )
        return str(zlib.crc32(hash_base.encode()))

    def _merge_hash_history(
        self,
        old_groups: list[list[str]],
        new_groups: list[list[str]],
        entry_count: int,
    ) -> list[list[str]] | None:
        """合并新旧哈希分组"""
        history_limit = self._resolve_hash_history_limit(entry_count)

        merged: list[list[str]] = []
        seen_identity: set[str] = set()

        for group in chain(new_groups, old_groups):
            if not group:
                continue
            identity = next((h for h in group if h.startswith("sid:")), None)
            if identity and identity in seen_identity:
                continue
            if identity:
                seen_identity.add(identity)
            merged.append(group)
            if len(merged) >= history_limit:
                break

        return merged or None

    def _resolve_hash_history_limit(self, entry_count: int) -> int:
        """计算哈希历史限制"""
        min_limit = self._hash_history_min
        multiplier = self._hash_history_multiplier
        hard_limit = self._hash_history_hard_limit
        absolute_max = self.HASH_HISTORY_ABSOLUTE_MAX

        min_limit = min(min_limit, absolute_max)
        multiplier = min(multiplier, absolute_max)
        hard_limit = min(hard_limit, absolute_max)
        hard_limit = max(hard_limit, min_limit)

        growth_limit = max(entry_count, 1) * multiplier
        return min(max(min_limit, growth_limit), hard_limit)
