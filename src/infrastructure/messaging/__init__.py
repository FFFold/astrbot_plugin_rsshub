"""消息推送包

提供消息发送和通知分发功能。
"""

from .message_sender import (
    BaseMessageSender,
    ChannelInfo,
    DirectMessageSender,
    ForwardMessageSender,
    MessageContext,
    MessageSender,
    SendResult,
    get_sender_for_platform,
)

__all__ = [
    "SendResult",
    "ChannelInfo",
    "MessageContext",
    "MessageSender",
    "BaseMessageSender",
    "DirectMessageSender",
    "ForwardMessageSender",
    "get_sender_for_platform",
]
