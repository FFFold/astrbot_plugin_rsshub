"""
通知分发服务

负责将 RSS 条目分发给订阅用户。
属于应用服务，负责编排领域服务和基础设施。
"""

from __future__ import annotations

from typing import Any

from ...domain.entities.push_history import PushHistory
from ...domain.repositories.push_history_repository import PushHistoryRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...infrastructure.utils import get_logger
from ..ports import MessageContext, MessageSenderProvider, SendRequest
from .session_push_queue import PushJob, SessionPushQueue

logger = get_logger()

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


def is_unrecoverable_error(error: str) -> bool:
    """判断错误是否为不可恢复类型（永久性失败，不应重试）"""
    if not error:
        return False
    lower_error = error.lower()
    return any(pattern in lower_error for pattern in UNRECOVERABLE_ERROR_PATTERNS)


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
        push_job_queue: SessionPushQueue | None = None,
    ):
        self._subscription_repo = subscription_repo
        self._push_history_repo = push_history_repo
        self._sender_provider = sender_provider
        self._push_job_queue = push_job_queue or SessionPushQueue()

    async def dispatch_to_feed_subscribers(
        self,
        feed_id: int,
        content: str,
        entry_title: str,
        entry_link: str,
        feed_title: str = "",
        feed_link: str = "",
        media_urls: list[str] | None = None,
        entry_guid: str | None = None,
        subscription_ids: list[int] | None = None,
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

        # 2. 为每个订阅创建推送历史记录并发送
        for sub in subscriptions:
            try:
                # 发送前指纹保护（dispatch_guard）
                # 检查是否已有相同 entry_guid 的成功推送记录
                already_sent = False
                if entry_guid:
                    existing_history = await self._push_history_repo.get_by_sub(
                        sub_id=sub.id,
                        limit=1,
                        status="success",
                    )
                    # 检查最近的成功推送中是否有相同的条目
                    for history in existing_history:
                        if history.entry_guid == entry_guid and history.is_success():
                            logger.debug(
                                "订阅 %s 已成功推送过条目 %s，跳过",
                                sub.id,
                                entry_guid,
                            )
                            already_sent = True
                            break
                    if already_sent:
                        continue

                # 创建推送历史记录
                history = PushHistory(
                    sub_id=sub.id,
                    user_id=sub.user_id,
                    feed_id=feed_id,
                    content=content,
                    entry_title=entry_title,
                    entry_link=entry_link,
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
                    subscription=sub,
                    content=content,
                    media_urls=media_urls,
                    job_description=f"feed={feed_id}, sub={sub.id}",
                )

                # 4. 更新推送状态
                if result["ok"]:
                    history.mark_success()
                    stats["success"] += 1
                elif result.get("cancelled"):
                    history.mark_failed(result.get("error", "Cancelled by /rss_stop"))
                    history.max_retries = 0
                    stats["failed"] += 1
                else:
                    # 首次失败不增加重试计数
                    history.record_first_failure(result.get("error", "Unknown error"))
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

    async def send_to_session(
        self,
        subscription,
        content: str,
        media_urls: list[str] | None,
        job_description: str = "",
    ) -> dict[str, Any]:
        """
        发送通知到指定订阅

        Args:
            subscription: 订阅对象
            content: 消息内容
            media_urls: 媒体 URL 列表
            job_description: 任务描述，用于队列和日志

        Returns:
            发送结果 {"ok": bool, "error": str}
        """
        try:
            # 获取平台对应的发送器
            sender = self._sender_provider.get(subscription.platform_name)

            # 构建目标会话 ID
            target_session = subscription.target_session
            if not target_session:
                logger.warning("订阅 %s 没有目标会话", subscription.id)
                return {"ok": False, "error": "No target session"}

            # 准备媒体
            media_items: list[tuple[str, str]] = []
            if media_urls:
                media_items = [("image", url) for url in media_urls]

            async def _send(job: PushJob):
                logger.debug(
                    "开始 RSS 推送任务: job_id=%s, session=%s, sub=%s",
                    job.job_id,
                    target_session,
                    subscription.id,
                )
                return await sender.send_to_user(
                    SendRequest(
                        session_id=target_session,
                        message=content,
                        media=media_items if media_items else None,
                    ),
                    context=MessageContext(
                        platform_name=subscription.platform_name or ""
                    ),
                )

            job_result = await self._push_job_queue.enqueue(
                target_session,
                _send,
                description=job_description,
            )

            if job_result.cancelled:
                logger.info(
                    "RSS 推送任务已取消: job_id=%s, session=%s, sub=%s",
                    job_result.job_id,
                    target_session,
                    subscription.id,
                )
                return {
                    "ok": False,
                    "cancelled": True,
                    "error": f"Cancelled by /rss_stop (job_id={job_result.job_id})",
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
                # 获取订阅信息
                sub = await self._subscription_repo.get_by_id(history.sub_id)
                if not sub or sub.state != 1:
                    logger.debug(
                        "订阅 %s 不存在或已禁用，跳过重试",
                        history.sub_id,
                    )
                    history.mark_failed("Subscription not available")
                    await self._push_history_repo.save(history)
                    stats["skipped"] += 1
                    continue

                # 重新发送
                result = await self.send_to_session(
                    subscription=sub,
                    content=history.content,
                    media_urls=None,  # 重试时不重新下载媒体
                    job_description=f"retry history={history.id}",
                )

                error_msg = result.get("error", "")
                if result["ok"]:
                    history.mark_success()
                    stats["success"] += 1
                elif result.get("cancelled"):
                    history.mark_failed(result.get("error", "Cancelled by /rss_stop"))
                    history.max_retries = 0
                    stats["failed"] += 1
                elif is_unrecoverable_error(error_msg):
                    # 不可恢复错误：直接标记为最终失败，不再重试
                    history.record_first_failure(error_msg)
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
                    stats["failed"] += 1

                await self._push_history_repo.save(history)

            except Exception as e:
                logger.error("重试推送 %s 失败: %s", history.id, e)
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
