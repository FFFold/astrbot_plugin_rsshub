"""消息发送器包

提供跨平台消息发送的实现。
"""

from .base_sender import DefaultMessageSender
from .factory import get_sender_for_platform, register_sender
from .onebot_sender import OneBotMessageSender
from .provider import (
    InfrastructureMessageSenderAdapter,
    InfrastructureMessageSenderProvider,
)
from .qq_official_sender import QQOfficialMessageSender
from .telegram_sender import TelegramMessageSender
from .types import (
    BaseMessageSender,
    ChannelInfo,
    MessageContext,
    PreparedMedia,
    SendResult,
    get_bot_self_id,
    set_bot_self_id_provider,
)
from .weixin_oc_sender import WeixinOCMessageSender

__all__ = [
    # 基础类型
    "BaseMessageSender",
    "SendResult",
    "PreparedMedia",
    "ChannelInfo",
    "MessageContext",
    # 发送器类
    "DefaultMessageSender",
    "TelegramMessageSender",
    "OneBotMessageSender",
    "QQOfficialMessageSender",
    "WeixinOCMessageSender",
    "InfrastructureMessageSenderAdapter",
    "InfrastructureMessageSenderProvider",
    # 工厂方法
    "get_sender_for_platform",
    "register_sender",
    # 工具函数
    "set_bot_self_id_provider",
    "get_bot_self_id",
]
