"""Telegram 消息发送器

针对 Telegram 平台的特定优化。
"""

from __future__ import annotations

from astrbot.api.message_components import Image, Plain, Video

from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .types import MessageContext, PreparedMedia, SendResult

logger = get_logger()


class TelegramMessageSender(DefaultMessageSender):
    """Telegram 平台消息发送器

    特性：
    - 支持单条消息发送多个图片
    - 媒体优先展示
    - 消息长度限制处理
    """

    # Telegram 限制
    MAX_MESSAGE_LENGTH = 4096
    MAX_MEDIA_PER_MESSAGE = 10

    @classmethod
    def _get_timeout_seconds(cls) -> int:
        """Telegram 可能需要更长的超时"""
        return max(1, int(getattr(cls, "_timeout_seconds", 60)))

    async def send_to_user(
        self,
        session_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        prepared_media: list[PreparedMedia] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到 Telegram 用户

        Telegram 特性：
        1. 支持单条消息发送最多 10 个媒体
        2. 媒体会优先显示，文字作为 caption
        """
        try:
            timeout = (
                context.timeout_seconds if context else self._get_timeout_seconds()
            )
            proxy = context.proxy if context else self._get_proxy()

            # 准备媒体
            effective_prepared = prepared_media
            if effective_prepared is None and media:
                effective_prepared = await self.prepare_media(
                    media, timeout=timeout, proxy=proxy
                )

            if effective_prepared:
                # 有媒体时，使用媒体优先策略
                return await self._send_with_media_first(
                    session_id, message, effective_prepared
                )

            # 无媒体，纯文本发送
            if message:
                return await self._send_text_only(session_id, message)

            return SendResult(ok=False, detail="empty_message")

        except Exception as err:
            logger.error("Telegram send failed: session=%s, error=%s", session_id, err)
            return SendResult(
                ok=False,
                transient=self._is_transient_network_error(err),
                detail=str(err),
            )

    async def _send_with_media_first(
        self,
        session_id: str,
        message: str,
        prepared_media: list[PreparedMedia],
    ) -> SendResult:
        """使用媒体优先策略发送

        Telegram 特性：
        - 单条消息可包含多个媒体（最多10个）
        - 文字作为 caption（最多 1024 字符）
        """
        from astrbot.core.message.message_event_result import MessageChain
        from astrbot.core.star.star_tools import StarTools

        # 分离媒体类型
        image_media = [m for m in prepared_media if m.media_type == "image"]
        video_media = [m for m in prepared_media if m.media_type == "video"]
        other_media = [
            m for m in prepared_media if m.media_type not in {"image", "video"}
        ]

        # 构建媒体组件（最多10个）
        media_components = []
        failed_urls = []

        for m in image_media[: self.MAX_MEDIA_PER_MESSAGE]:
            if m.download_failed or not m.local_path:
                failed_urls.append(m.original_url)
                continue
            media_components.append(Image(file=str(m.local_path)))

        # 视频也计入媒体数量
        remaining = self.MAX_MEDIA_PER_MESSAGE - len(media_components)
        for m in video_media[:remaining]:
            if m.download_failed or not m.local_path:
                failed_urls.append(m.original_url)
                continue
            media_components.append(Video(file=str(m.local_path)))

        if not media_components:
            # 没有成功准备的媒体，退化为纯文本
            if failed_urls:
                message = self._append_failed_media_links(message, failed_urls)
            return await self._send_text_only(session_id, message)

        # 构建消息链：媒体 + 文字（作为 caption）
        chain = media_components.copy()

        # caption 限制 1024 字符
        caption = message[:1024] if message else ""
        if caption:
            chain.append(Plain(caption))

        # 发送媒体消息
        try:
            message_chain = MessageChain(chain=chain)
            sent = await StarTools.send_message(session_id, message_chain)
            if sent:
                logger.debug(
                    "Telegram media sent: session=%s, media_count=%s",
                    session_id,
                    len(media_components),
                )
                return SendResult(ok=True)
            else:
                return SendResult(ok=False, detail="telegram_send_failed")
        except Exception as ex:
            logger.warning("Telegram media send failed, fallback to text: %s", ex)
            # 失败时回退到纯文本
            if failed_urls:
                message = self._append_failed_media_links(message, failed_urls)
            return await self._send_text_only(session_id, message)

    async def _send_text_only(self, session_id: str, message: str) -> SendResult:
        """发送纯文本消息（处理长度限制）"""
        from astrbot.api.message_components import Plain
        from astrbot.core.message.message_event_result import MessageChain
        from astrbot.core.star.star_tools import StarTools

        # Telegram 消息长度限制 4096
        if len(message) > self.MAX_MESSAGE_LENGTH:
            message = message[: self.MAX_MESSAGE_LENGTH - 3] + "..."

        chain = [Plain(message)]
        message_chain = MessageChain(chain=chain)

        try:
            sent = await StarTools.send_message(session_id, message_chain)
            if sent:
                return SendResult(ok=True)
            else:
                return SendResult(ok=False, detail="telegram_text_send_failed")
        except Exception as ex:
            logger.error("Telegram text send failed: %s", ex)
            return SendResult(ok=False, detail=str(ex))
