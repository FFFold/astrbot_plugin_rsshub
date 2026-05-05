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
from .plugin_manager import (
    Extension,
    PluginManager,
    get_plugin_manager,
    on_event,
    reset_plugin_manager,
)
from .senders import (
    BaseMessageSender,
    ChannelInfo,
    DefaultMessageSender,
    MessageContext,
    OneBotMessageSender,
    PreparedMedia,
    QQOfficialMessageSender,
    SendResult,
    TelegramMessageSender,
    WechatMessageSender,
    get_sender_for_platform,
    register_sender,
    get_bot_self_id,
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
    # Plugin Manager
    "Extension",
    "PluginManager",
    "get_plugin_manager",
    "reset_plugin_manager",
    "on_event",
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
    "WechatMessageSender",
    "get_sender_for_platform",
    "register_sender",
    "get_bot_self_id",
    "set_bot_self_id_provider",
    # Notification
    "NotificationServiceImpl",
    "get_notification_service",
]
