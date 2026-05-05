"""微信消息发送器

针对微信的特定优化。
"""

from __future__ import annotations

from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .types import MessageContext, PreparedMedia, SendResult

logger = get_logger()


class WechatMessageSender(DefaultMessageSender):
    """微信平台消息发送器

    特性：
    - 特定的媒体处理
    - 消息长度限制
    """

    # 微信限制
    MAX_MESSAGE_LENGTH = 2000

    async def send_to_user(
        self,
        session_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        prepared_media: list[PreparedMedia] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到微信"""
        # TODO: 实现微信特定逻辑
        logger.debug("Wechat sender: session=%s", session_id)
        return await super().send_to_user(
            session_id, message, media, prepared_media, context
        )
