"""QQ 官方 Bot 消息发送器

针对 QQ 官方 Bot 的特定优化。
"""

from __future__ import annotations

from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .types import MessageContext, PreparedMedia, SendResult

logger = get_logger()


class QQOfficialMessageSender(DefaultMessageSender):
    """QQ 官方 Bot 消息发送器

    特性：
    - 支持 Markdown 消息
    - 支持按钮
    - 特定的媒体处理
    """

    # QQ 官方限制
    MAX_MESSAGE_LENGTH = 2000

    async def send_to_user(
        self,
        session_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        prepared_media: list[PreparedMedia] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到 QQ 官方 Bot"""
        # TODO: 实现 QQ 官方 Bot 特定逻辑
        logger.debug("QQ Official sender: session=%s", session_id)
        return await super().send_to_user(
            session_id, message, media, prepared_media, context
        )
