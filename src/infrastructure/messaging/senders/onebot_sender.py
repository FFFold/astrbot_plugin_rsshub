"""QQ OneBot 消息发送器

针对 QQ OneBot 协议的特定优化。
"""

from __future__ import annotations

from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .types import MessageContext, PreparedMedia, SendResult

logger = get_logger()


class OneBotMessageSender(DefaultMessageSender):
    """QQ OneBot 平台消息发送器

    特性：
    - 支持合并转发（Nodes）
    - 支持 CQ 码
    - 长消息自动分段
    """

    # OneBot 限制
    MAX_MESSAGE_LENGTH = 2000
    MAX_MEDIA_PER_MESSAGE = 10

    async def send_to_user(
        self,
        session_id: str,
        message: str,
        media: list[tuple[str, str]] | None = None,
        prepared_media: list[PreparedMedia] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息到 QQ OneBot 用户"""
        # TODO: 实现 OneBot 特定逻辑
        # 1. 支持合并转发 Nodes
        # 2. 处理 CQ 码
        # 3. 长消息分段
        logger.debug("OneBot sender: session=%s", session_id)
        return await super().send_to_user(
            session_id, message, media, prepared_media, context
        )
