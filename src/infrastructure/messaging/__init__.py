"""消息推送包

提供消息发送和通知分发功能。所有发送器实现位于 senders/ 子包。
"""

from .event_bus import (
    BaseEvent,
    DeduplicationEvent,
    EntryProcessEvent,
    EventBus,
    FeedFetchEvent,
    FeedParseEvent,
    MessageFormatEvent,
    MessageSendEvent,
    MessageSentEvent,
    get_event_bus,
    reset_event_bus,
)
from .notification_service import NotificationServiceImpl, get_notification_service
from .senders import (
    BaseMessageSender,
    ChannelInfo,
    DefaultMessageSender,
    InfrastructureMessageSenderAdapter,
    InfrastructureMessageSenderProvider,
    MessageContext,
    OneBotMessageSender,
    PreparedMedia,
    QQOfficialMessageSender,
    SendResult,
    TelegramMessageSender,
    WeixinOCMessageSender,
    get_bot_self_id,
    get_sender_for_platform,
    register_sender,
    set_bot_self_id_provider,
)

__all__ = [
    # Event System
    "BaseEvent",
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    "FeedFetchEvent",
    "FeedParseEvent",
    "EntryProcessEvent",
    "MessageFormatEvent",
    "MessageSendEvent",
    "MessageSentEvent",
    "DeduplicationEvent",
    # Senders
    "SendResult",
    "PreparedMedia",
    "ChannelInfo",
    "MessageContext",
    "BaseMessageSender",
    "DefaultMessageSender",
    "TelegramMessageSender",
    "OneBotMessageSender",
    "QQOfficialMessageSender",
    "WeixinOCMessageSender",
    "InfrastructureMessageSenderAdapter",
    "InfrastructureMessageSenderProvider",
    "get_sender_for_platform",
    "register_sender",
    "get_bot_self_id",
    "set_bot_self_id_provider",
    # Notification
    "NotificationServiceImpl",
    "get_notification_service",
]
