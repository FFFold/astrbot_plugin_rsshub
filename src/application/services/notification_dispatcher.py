"""
通知分发服务

负责将 RSS 条目分发给订阅用户。
属于应用服务，负责编排领域服务和基础设施。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from ...domain.entities.push_history import PushHistory
from ...domain.repositories.push_history_repository import PushHistoryRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...domain.repositories.user_repository import UserRepository
from ...infrastructure.pipeline import MessageFormatter
from ...infrastructure.utils import get_logger
from ..ports import MessageContext, MessageSenderProvider, SendRequest
from .content_handlers import ContentHandlerRuntime, EntryContentContext
from .session_push_queue import PushJob, SessionPushQueue

logger = get_logger()
_message_formatter = MessageFormatter()

# 不可恢复错误关键词（匹配时不计入重试，直接标记为 failed）
UNRECOVERABLE_ERROR_PATTERNS: tuple[str, ...] = (
    "no target session",
    "target session is empty",
    "invalid session",
    "session not found",
    "user banned",
    "user is banned",
    "permission denied",
    "no permission",
    "forbidden",
    "not found",
    "invalid target",
)

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")
VIDEO_EXTENSIONS = (".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".m3u8")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
SUPPORTED_MEDIA_TYPES = {"image", "audio", "video", "file"}


@dataclass(frozen=True)
class SendTarget:
    """Minimal runtime target for a push operation."""

    user_id: str
    platform_name: str | None
    target_session: str | None
    sub_id: int | None = None


def is_unrecoverable_error(error: str) -> bool:
    """判断错误是否为不可恢复类型（永久性失败，不应重试）"""
    if not error:
        return False
    lower_error = error.lower()
    return any(pattern in lower_error for pattern in UNRECOVERABLE_ERROR_PATTERNS)


def infer_media_type(url: str) -> str:
    """Infer the message component type for a media URL.

    RSSHub often wraps source media as `...?url=<encoded source>`, so check both
    the visible path and wrapped URL query values before falling back to image.
    """
    candidates = [url]
    try:
        parsed = urlparse(url)
        candidates.append(unquote(parsed.path or ""))
        candidates.extend(parse_qs(parsed.query).get("url", []))
    except Exception:
        pass

    for candidate in candidates:
        lowered = unquote(candidate).lower()
        parsed_path = urlparse(lowered).path if "://" in lowered else lowered
        if parsed_path.endswith(IMAGE_EXTENSIONS):
            return "image"
        if parsed_path.endswith(VIDEO_EXTENSIONS):
            return "video"
        if parsed_path.endswith(AUDIO_EXTENSIONS):
            return "audio"

    return "image"


def normalize_media_items(
    media_urls: list[str] | None = None,
    media_items: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """Build sender media tuples, preserving explicit types before URL inference."""
    normalized: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    def append(media_type: str, url: str) -> None:
        media_url = str(url or "").strip()
        if not media_url or media_url in seen_urls:
            return
        effective_type = str(media_type or "").strip().lower()
        if effective_type not in SUPPORTED_MEDIA_TYPES:
            effective_type = infer_media_type(media_url)
        normalized.append((effective_type, media_url))
        seen_urls.add(media_url)

    for media_type, media_url in media_items or []:
        append(media_type, media_url)

    for media_url in media_urls or []:
        append(infer_media_type(media_url), media_url)

    return normalized


def append_media_links_to_text(
    text: str,
    media_items: list[tuple[str, str]] | None = None,
    media_urls: list[str] | None = None,
) -> str:
    """Append original media URLs to text for failure-facing output."""
    normalized = normalize_media_items(media_urls=media_urls, media_items=media_items)
    if not normalized:
        return text
    urls = [url for _media_type, url in normalized]
    if text and "媒体原始链接:" in text:
        existing_lines = {line.strip() for line in text.splitlines() if line.strip()}
        if "媒体原始链接:" in existing_lines and all(
            url in existing_lines for url in urls
        ):
            return text
    return _message_formatter._append_failed_links(text, urls)


def strip_appended_media_links_from_text(
    text: str,
    media_items: list[tuple[str, str]] | None = None,
    media_urls: list[str] | None = None,
) -> str:
    """Remove the failure-facing media URL suffix before retry send."""
    if not text:
        return text
    normalized = normalize_media_items(media_urls=media_urls, media_items=media_items)
    if not normalized:
        return text

    suffix_lines = ["媒体原始链接:", *[url for _media_type, url in normalized]]
    lines = text.splitlines()
    if len(lines) < len(suffix_lines):
        return text
    if lines[-len(suffix_lines) :] != suffix_lines:
        return text

    trimmed_lines = lines[: -len(suffix_lines)]
    while trimmed_lines and not trimmed_lines[-1].strip():
        trimmed_lines.pop()
    return "\n".join(trimmed_lines)


def build_agent_entry_guid(
    *,
    source_key: str,
    user_id: str,
    target_session: str,
    title: str,
    link: str,
    xml: str,
    media_items: list[tuple[str, str]] | None = None,
) -> str:
    """Build a stable idempotency key for agent-originated pushes."""
    normalized_media = normalize_media_items(media_items=media_items)
    payload = "\n".join(
        [
            source_key.strip(),
            user_id.strip(),
            target_session.strip(),
            title.strip(),
            link.strip(),
            xml.strip(),
            *[f"{media_type}:{url}" for media_type, url in normalized_media],
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"agent:{digest}"


class NotificationDispatcher:
    """
    通知分发服务

    负责将 RSS 条目分发给订阅用户。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        push_history_repo: PushHistoryRepository,
        sender_provider: MessageSenderProvider,
        user_repo: UserRepository | None = None,
        push_job_queue: SessionPushQueue | None = None,
        content_handler_runtime: ContentHandlerRuntime | None = None,
    ):
        self._subscription_repo = subscription_repo
        self._user_repo = user_repo
        self._push_history_repo = push_history_repo
        self._sender_provider = sender_provider
        self._push_job_queue = push_job_queue or SessionPushQueue()
        self._content_handler_runtime = (
            content_handler_runtime or ContentHandlerRuntime()
        )

    @staticmethod
    def _target_from_subscription(subscription) -> SendTarget:
        return SendTarget(
            user_id=subscription.user_id,
            platform_name=subscription.platform_name,
            target_session=subscription.target_session,
            sub_id=subscription.id,
        )

    @staticmethod
    def _feed_source_key(feed_id: int, sub_id: int | None) -> str:
        return f"feed:{feed_id}:sub:{sub_id or 0}"

    async def dispatch_to_feed_subscribers(
        self,
        feed_id: int,
        content: str,
        entry_title: str,
        entry_link: str,
        feed_title: str = "",
        feed_link: str = "",
        media_urls: list[str] | None = None,
        media_items: list[tuple[str, str]] | None = None,
        entry_guid: str | None = None,
        subscription_ids: list[int] | None = None,
        raw_entry: EntryContentContext | None = None,
    ) -> dict[str, int]:
        """
        将条目分发给 Feed 的所有订阅者

        Args:
            feed_id: Feed ID
            content: 格式化后的消息内容
            entry_title: 条目标题
            entry_link: 条目链接
            feed_title: Feed 标题
            feed_link: Feed 链接
            media_urls: 媒体 URL 列表
            media_items: 已知类型的媒体列表，格式为 (image/audio/video/file, url)
            entry_guid: 条目 GUID
            subscription_ids: 限定分发的订阅 ID；为空时分发到所有活跃订阅

        Returns:
            统计信息字典 {success: x, failed: y, pending: z}
        """
        stats = {"success": 0, "failed": 0, "pending": 0}

        # 1. 获取 Feed 的所有启用订阅
        subscriptions = await self._subscription_repo.get_active_by_feed_id(feed_id)
        if subscription_ids is not None:
            wanted = set(subscription_ids)
            subscriptions = [sub for sub in subscriptions if sub.id in wanted]
        if not subscriptions:
            if subscription_ids is None:
                logger.debug("Feed %s 没有活跃的订阅", feed_id)
            else:
                logger.debug(
                    "Feed %s 没有匹配的活跃订阅: %s",
                    feed_id,
                    subscription_ids,
                )
            return stats

        logger.info(
            "分发条目到 %s 个订阅者: feed_id=%s, title=%s",
            len(subscriptions),
            feed_id,
            entry_title[:50],
        )

        normalized_media = normalize_media_items(
            media_urls=media_urls,
            media_items=media_items,
        )
        persisted_media_urls = [url for _media_type, url in normalized_media]

        # 2. 为每个订阅创建推送历史记录并发送
        for sub in subscriptions:
            try:
                user = (
                    await self._user_repo.get_by_id(sub.user_id)
                    if self._user_repo is not None
                    else None
                )
                processed_entry = raw_entry
                if processed_entry is not None:
                    processed_entry = await self._content_handler_runtime.process_entry(
                        subscription=sub,
                        user=user,
                        entry=processed_entry,
                        session_id=str(sub.target_session or "").strip() or None,
                    )

                effective_title = (
                    processed_entry.title
                    if processed_entry is not None
                    else entry_title
                )
                effective_link = (
                    processed_entry.link if processed_entry is not None else entry_link
                )
                effective_content = (
                    self._format_entry_content(processed_entry)
                    if processed_entry is not None
                    else content
                )

                # 发送前指纹保护（dispatch_guard）
                # 检查是否已有相同 entry_guid 的成功推送记录
                if entry_guid:
                    already_sent = (
                        await self._push_history_repo.exists_success_by_scope_and_guid(
                            source_type="feed",
                            source_key=self._feed_source_key(feed_id, sub.id),
                            user_id=sub.user_id,
                            target_session=str(sub.target_session or ""),
                            entry_guid=entry_guid,
                        )
                    )
                    if already_sent:
                        logger.debug(
                            "订阅 %s 已成功推送过条目 %s，跳过", sub.id, entry_guid
                        )
                        continue

                # 创建推送历史记录
                history = PushHistory(
                    sub_id=sub.id,
                    user_id=sub.user_id,
                    feed_id=feed_id,
                    source_type="feed",
                    source_key=self._feed_source_key(feed_id, sub.id),
                    content=effective_content,
                    raw_xml=(
                        str(processed_entry.raw_xml or "").strip()
                        if processed_entry is not None
                        else None
                    )
                    or None,
                    media_urls=persisted_media_urls or None,
                    entry_title=effective_title,
                    entry_link=effective_link,
                    entry_guid=entry_guid,
                    feed_title=feed_title,
                    feed_link=feed_link,
                    platform_name=sub.platform_name,
                    target_session=sub.target_session,
                    status="pending",
                    retry_count=0,
                    max_retries=3,
                )

                # 保存到数据库
                history = await self._push_history_repo.save(history)

                # 3. 调用消息发送器发送消息
                result = await self.send_to_session(
                    target=self._target_from_subscription(sub),
                    content=effective_content,
                    media_urls=media_urls,
                    media_items=media_items,
                    job_description=f"feed={feed_id}, sub={sub.id}",
                    channel_title=feed_title,
                    channel_link=feed_link,
                    feed_id=feed_id,
                    sub_id=sub.id,
                )

                # 4. 更新推送状态
                if result["ok"]:
                    history.mark_success()
                    stats["success"] += 1
                elif result.get("cancelled"):
                    history.mark_stopped(result.get("error", "Stopped by /sub_stop"))
                    history.max_retries = 0
                    stats["success"] += 1
                else:
                    # 首次失败不增加重试计数
                    history.record_first_failure(result.get("error"))
                    history.content = append_media_links_to_text(
                        history.content,
                        media_items=normalized_media,
                    )
                    if history.can_retry():
                        stats["pending"] += 1
                    else:
                        stats["failed"] += 1

                await self._push_history_repo.save(history)

            except Exception as e:
                logger.error(
                    "分发到订阅 %s 失败: %s",
                    sub.id,
                    e,
                    exc_info=True,
                )
                stats["failed"] += 1

        logger.info(
            "分发完成: success=%s, failed=%s, pending=%s",
            stats["success"],
            stats["failed"],
            stats["pending"],
        )
        return stats

    async def dispatch_agent_entry(
        self,
        *,
        source_key: str,
        target: SendTarget,
        content: str,
        raw_xml: str = "",
        entry_title: str,
        entry_link: str = "",
        feed_title: str = "",
        feed_link: str = "",
        media_urls: list[str] | None = None,
        media_items: list[tuple[str, str]] | None = None,
        entry_guid: str,
    ) -> dict[str, Any]:
        """Dispatch one agent-originated push while preserving history and retries."""
        normalized_media = normalize_media_items(
            media_urls=media_urls,
            media_items=media_items,
        )
        persisted_media_urls = [url for _media_type, url in normalized_media]
        target_session = str(target.target_session or "").strip()
        if not target_session:
            return {"ok": False, "error": "No target session", "deduplicated": False}

        already_sent = await self._push_history_repo.exists_success_by_scope_and_guid(
            source_type="agent",
            source_key=source_key,
            user_id=target.user_id,
            target_session=target_session,
            entry_guid=entry_guid,
        )
        if already_sent:
            return {
                "ok": True,
                "deduplicated": True,
                "stats": {"success": 0, "failed": 0, "pending": 0},
            }

        history = PushHistory(
            sub_id=None,
            user_id=target.user_id,
            feed_id=None,
            source_type="agent",
            source_key=source_key,
            content=content,
            raw_xml=str(raw_xml or "").strip() or None,
            media_urls=persisted_media_urls or None,
            entry_title=entry_title,
            entry_link=entry_link,
            entry_guid=entry_guid,
            feed_title=feed_title,
            feed_link=feed_link,
            platform_name=target.platform_name,
            target_session=target.target_session,
            status="pending",
            retry_count=0,
            max_retries=3,
        )
        history = await self._push_history_repo.save(history)

        result = await self.send_to_session(
            target=target,
            content=content,
            media_urls=media_urls,
            media_items=media_items,
            job_description=f"agent={source_key}, history={history.id}",
            channel_title=feed_title,
            channel_link=feed_link,
            feed_id=None,
            sub_id=None,
        )

        stats = {"success": 0, "failed": 0, "pending": 0}
        if result["ok"]:
            history.mark_success()
            stats["success"] = 1
        elif result.get("cancelled"):
            history.mark_stopped(result.get("error", "Stopped by /sub_stop"))
            history.max_retries = 0
            stats["success"] = 1
        else:
            history.record_first_failure(result.get("error"))
            history.content = append_media_links_to_text(
                history.content,
                media_items=normalized_media,
            )
            stats["pending" if history.can_retry() else "failed"] = 1

        await self._push_history_repo.save(history)
        return {
            "ok": result["ok"],
            "deduplicated": False,
            "stats": stats,
            "history_id": history.id,
        }

    async def send_to_session(
        self,
        *,
        target: SendTarget,
        content: str,
        media_urls: list[str] | None,
        media_items: list[tuple[str, str]] | None = None,
        job_description: str = "",
        channel_title: str = "",
        channel_link: str = "",
        feed_id: int | None = None,
        sub_id: int | None = None,
    ) -> dict[str, Any]:
        """
        发送通知到指定目标

        Args:
            target: 推送目标
            content: 消息内容
            media_urls: 媒体 URL 列表
            media_items: 已知类型的媒体列表，格式为 (image/audio/video/file, url)
            job_description: 任务描述，用于队列和日志

        Returns:
            发送结果 {"ok": bool, "error": str}
        """
        try:
            # 获取平台对应的发送器
            sender = self._sender_provider.get(target.platform_name)

            # 构建目标会话 ID
            target_session = target.target_session
            if not target_session:
                logger.warning("推送目标 %s 没有目标会话", target.user_id)
                return {"ok": False, "error": "No target session"}

            # 准备媒体；优先保留 HTML/RSS 已解析出的准确类型。
            normalized_media = normalize_media_items(
                media_urls=media_urls,
                media_items=media_items,
            )

            async def _send(job: PushJob):
                logger.debug(
                    "开始 RSS 推送任务: job_id=%s, session=%s, sub=%s",
                    job.job_id,
                    target_session,
                    target.sub_id,
                )
                return await sender.send_to_user(
                    SendRequest(
                        session_id=target_session,
                        message=content,
                        media=normalized_media if normalized_media else None,
                    ),
                    context=MessageContext(
                        channel_title=channel_title,
                        channel_link=channel_link,
                        platform_name=target.platform_name or "",
                    ),
                )

            job_result = await self._push_job_queue.enqueue(
                target_session,
                _send,
                description=job_description,
                feed_id=feed_id,
                feed_title=channel_title or "",
                sub_id=sub_id,
            )

            if job_result.cancelled:
                logger.info(
                    "RSS 推送任务已取消: job_id=%s, session=%s, sub=%s",
                    job_result.job_id,
                    target_session,
                    target.sub_id,
                )
                return {
                    "ok": False,
                    "cancelled": True,
                    "error": f"Cancelled by /sub_stop (job_id={job_result.job_id})",
                    "job_id": job_result.job_id,
                }

            if not job_result.ok or job_result.value is None:
                return {
                    "ok": False,
                    "error": job_result.error or "Push job failed",
                    "job_id": job_result.job_id,
                }

            result = job_result.value
            logger.debug(
                "RSS 推送任务完成: job_id=%s, session=%s, ok=%s",
                job_result.job_id,
                target_session,
                result.ok,
            )
            return {
                "ok": result.ok,
                "error": result.detail if not result.ok else "",
                "job_id": job_result.job_id,
            }

        except Exception as e:
            logger.error("发送通知失败: %s", e, exc_info=True)
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _format_entry_content(entry: EntryContentContext) -> str:
        title = str(entry.title or "").strip()
        body = str(entry.content or entry.summary or "").strip()
        link = str(entry.link or "").strip()
        feed_title = str(entry.feed_title or "").strip()
        feed_link = str(entry.feed_link or "").strip()
        author = str(entry.author or "").strip()
        if title and body and body != title:
            content = f"{title}\n\n{body}"
        else:
            content = body or title
        via_suffix = f"via {link} | {feed_title or feed_link}"
        if author:
            via_suffix += f" (author: {author})"
        return f"{content}\n\n{via_suffix}"

    async def dispatch_pending_retries(self, limit: int = 100) -> dict[str, int]:
        """
        分发待重试的推送

        Args:
            limit: 最大处理数量

        Returns:
            统计信息字典 {success: x, failed: y, skipped: z}
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}

        # 原子获取并标记为 retrying，防止多 worker 重复拉取同一批记录
        pending = await self._push_history_repo.get_and_mark_retrying(limit)
        if not pending:
            return stats

        logger.info("处理 %s 个待重试推送", len(pending))

        for history in pending:
            try:
                target: SendTarget | None = None
                if history.source_type == "agent":
                    target = SendTarget(
                        user_id=history.user_id,
                        platform_name=history.platform_name,
                        target_session=history.target_session,
                        sub_id=None,
                    )
                else:
                    sub = await self._subscription_repo.get_by_id(
                        int(history.sub_id or 0)
                    )
                    if not sub or sub.state != 1:
                        logger.debug(
                            "订阅 %s 不存在或已禁用，跳过重试",
                            history.sub_id,
                        )
                        history.mark_failed("Subscription not available")
                        await self._push_history_repo.save(history)
                        stats["skipped"] += 1
                        continue
                    target = self._target_from_subscription(sub)

                # 重新发送
                result = await self.send_to_session(
                    target=target,
                    content=strip_appended_media_links_from_text(
                        history.content,
                        media_urls=history.media_urls,
                    ),
                    media_urls=history.media_urls,
                    job_description=f"retry history={history.id}",
                    channel_title=history.feed_title,
                    channel_link=history.feed_link,
                    feed_id=history.feed_id,
                    sub_id=history.sub_id,
                )

                error_msg = result.get("error", "")
                if result["ok"]:
                    history.content = strip_appended_media_links_from_text(
                        history.content,
                        media_urls=history.media_urls,
                    )
                    history.mark_success()
                    stats["success"] += 1
                elif result.get("cancelled"):
                    history.mark_stopped(result.get("error", "Stopped by /sub_stop"))
                    history.max_retries = 0
                    stats["success"] += 1
                elif is_unrecoverable_error(error_msg):
                    # 不可恢复错误：直接标记为最终失败，不再重试
                    history.record_first_failure(error_msg)
                    history.content = append_media_links_to_text(
                        history.content,
                        media_urls=history.media_urls,
                    )
                    # 覆盖 max_retries 为 0，防止 can_retry 仍返回 True
                    history.max_retries = 0
                    stats["failed"] += 1
                    logger.warning(
                        "订阅 %s 推送失败（不可恢复）: %s",
                        history.sub_id,
                        error_msg,
                    )
                else:
                    # 可恢复错误：记录重试失败，增加计数
                    history.record_retry_failure(error_msg)
                    history.content = append_media_links_to_text(
                        history.content,
                        media_urls=history.media_urls,
                    )
                    stats["failed"] += 1

                await self._push_history_repo.save(history)

            except Exception as e:
                logger.error("重试推送 %s 失败: %s", history.id, e)
                history.record_retry_failure(str(e))
                await self._push_history_repo.save(history)
                stats["failed"] += 1

        logger.info(
            "重试完成: success=%s, failed=%s, skipped=%s",
            stats["success"],
            stats["failed"],
            stats["skipped"],
        )
        return stats

    async def get_push_stats(self) -> dict[str, int]:
        """
        获取推送统计信息

        Returns:
            统计信息字典
        """
        return await self._push_history_repo.get_stats()

    async def cleanup_old_records(self, days: int = 30) -> int:
        """
        清理指定天数前的历史记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数量
        """
        return await self._push_history_repo.delete_old_records(days)
