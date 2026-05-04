"""
通知分发服务

负责将 RSS 条目分发给订阅用户。
属于应用服务，负责编排领域服务和基础设施。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ...domain.entities.push_history import PushHistory
from ...domain.repositories.push_history_repository import PushHistoryRepository
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...infrastructure.messaging.senders.factory import get_sender_for_platform
from ...infrastructure.utils import get_logger

if TYPE_CHECKING:
    from ...infrastructure.messaging.senders.types import BaseMessageSender

logger = get_logger()


class NotificationDispatcher:
    """
    通知分发服务

    负责将 RSS 条目分发给订阅用户。
    """

    def __init__(
        self,
        subscription_repo: SubscriptionRepository,
        push_history_repo: PushHistoryRepository,
    ):
        self._subscription_repo = subscription_repo
        self._push_history_repo = push_history_repo

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

        Returns:
            统计信息字典 {success: x, failed: y, pending: z}
        """
        stats = {"success": 0, "failed": 0, "pending": 0}

        # 1. 获取 Feed 的所有启用订阅
        subscriptions = await self._subscription_repo.get_active_by_feed_id(feed_id)
        if not subscriptions:
            logger.debug("Feed %s 没有活跃的订阅", feed_id)
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
                result = await self._send_notification(
                    subscription=sub,
                    content=content,
                    media_urls=media_urls,
                    history=history,
                )

                # 4. 更新推送状态
                if result["ok"]:
                    history.mark_success()
                    stats["success"] += 1
                else:
                    history.mark_failed(result.get("error", "Unknown error"))
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

    async def _send_notification(
        self,
        subscription,
        content: str,
        media_urls: list[str] | None,
        history: PushHistory,
    ) -> dict:
        """
        发送通知到指定订阅

        Args:
            subscription: 订阅对象
            content: 消息内容
            media_urls: 媒体 URL 列表
            history: 推送历史记录

        Returns:
            发送结果 {"ok": bool, "error": str}
        """
        try:
            # 获取平台对应的发送器
            sender_class = get_sender_for_platform(subscription.platform_name)
            sender: BaseMessageSender = sender_class()

            # 构建目标会话 ID
            target_session = subscription.target_session
            if not target_session:
                logger.warning("订阅 %s 没有目标会话", subscription.id)
                return {"ok": False, "error": "No target session"}

            # 准备媒体
            media_items: list[tuple[str, str]] = []
            if media_urls:
                media_items = [("image", url) for url in media_urls]

            # 发送消息
            # 注意：这里使用新的 sender 系统
            from ...infrastructure.messaging.senders.types import MessageContext

            context = MessageContext(
                platform_name=subscription.platform_name or "",
            )

            result = await sender.send_to_user(
                session_id=target_session,
                message=content,
                media=media_items if media_items else None,
                context=context,
            )

            return {
                "ok": result.ok,
                "error": result.detail if not result.ok else "",
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
            统计信息字典 {success: x, failed: y}
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}

        pending = await self._push_history_repo.get_pending_for_retry(limit)
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
                    stats["skipped"] += 1
                    continue

                # 重新发送
                result = await self._send_notification(
                    subscription=sub,
                    content=history.content,
                    media_urls=None,  # 重试时不重新下载媒体
                    history=history,
                )

                # 更新状态
                if result["ok"]:
                    history.mark_success()
                    stats["success"] += 1
                else:
                    history.mark_failed(result.get("error", "Retry failed"))
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
