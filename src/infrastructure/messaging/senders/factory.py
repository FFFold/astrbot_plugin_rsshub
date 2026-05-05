"""发送器工厂

根据平台类型获取对应的消息发送器。
"""

from __future__ import annotations

from ...config import get_config_manager
from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .onebot_sender import OneBotMessageSender
from .qq_official_sender import QQOfficialMessageSender
from .telegram_sender import TelegramMessageSender
from .types import BaseMessageSender
from .wechat_sender import WechatMessageSender

logger = get_logger()

# 发送器映射表
_SENDER_MAP: dict[str, type[DefaultMessageSender]] = {
    "telegram": TelegramMessageSender,
    "tg": TelegramMessageSender,
    "aiocqhttp": OneBotMessageSender,
    "onebot": OneBotMessageSender,
    "onebot11": OneBotMessageSender,
    "onebotv11": OneBotMessageSender,
    "qq_official": QQOfficialMessageSender,
    "qqofficial": QQOfficialMessageSender,
    "qq": QQOfficialMessageSender,
    "wechat": WechatMessageSender,
    "weixin": WechatMessageSender,
    "weixin_oc": WechatMessageSender,
}


def get_sender_for_platform(platform_name: str | None) -> type[DefaultMessageSender]:
    """根据平台类型获取消息发送器

    Args:
        platform_name: 平台类型名称，如 "telegram", "aiocqhttp" 等

    Returns:
        对应的消息发送器类
    """
    if not platform_name:
        return DefaultMessageSender

    normalized = platform_name.strip().lower()

    # 检查配置中是否禁用了特定发送器
    try:
        config = get_config_manager()
        if config and hasattr(config, 'sender_strategies'):
            strategies = config.sender_strategies
            # 根据平台检查是否启用
            if normalized in {"telegram", "tg"} and not getattr(strategies, 'telegram', True):
                logger.debug("Telegram sender disabled by config")
                return DefaultMessageSender
            if normalized in {"aiocqhttp", "onebot", "onebot11", "onebotv11"}:
                if not getattr(strategies, 'aiocqhttp', True):
                    logger.debug("OneBot sender disabled by config")
                    return DefaultMessageSender
            if normalized in {"qq_official", "qqofficial", "qq"}:
                if not getattr(strategies, 'qq_official', True):
                    logger.debug("QQ Official sender disabled by config")
                    return DefaultMessageSender
            if normalized in {"wechat", "weixin", "weixin_oc"}:
                if not getattr(strategies, 'weixin_oc', True):
                    logger.debug("WeChat sender disabled by config")
                    return DefaultMessageSender
    except Exception:
        # 配置未初始化，使用默认
        pass

    # 查找对应的发送器
    sender_class = _SENDER_MAP.get(normalized)
    if sender_class:
        logger.debug("Found sender for platform '%s': %s", platform_name, sender_class.__name__)
        return sender_class

    # 尝试模糊匹配
    for key, sender_cls in _SENDER_MAP.items():
        if key in normalized:
            logger.debug("Fuzzy matched sender for '%s': %s", platform_name, sender_cls.__name__)
            return sender_cls

    logger.debug("No specific sender found for '%s', using default", platform_name)
    return DefaultMessageSender


def register_sender(platform: str, sender_class: type[DefaultMessageSender]) -> None:
    """注册自定义发送器

    Args:
        platform: 平台标识
        sender_class: 发送器类
    """
    _SENDER_MAP[platform.lower()] = sender_class
    logger.info("Registered custom sender for platform '%s': %s", platform, sender_class.__name__)
