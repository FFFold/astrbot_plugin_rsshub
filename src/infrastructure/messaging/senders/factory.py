"""发送器工厂

根据平台类型获取对应的消息发送器。
"""

from __future__ import annotations

from ....application.settings import SenderStrategySettings
from ...config import get_config_manager
from ...utils import get_logger
from .base_sender import DefaultMessageSender
from .onebot_sender import OneBotMessageSender
from .qq_official_sender import QQOfficialMessageSender
from .telegram_sender import TelegramMessageSender

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
    # 微信官方 Bot 直接使用默认发送器，官方适配器已处理所有逻辑
    "wechat": DefaultMessageSender,
    "weixin": DefaultMessageSender,
    "weixin_oc": DefaultMessageSender,
}


def _get_legacy_sender_strategies() -> SenderStrategySettings | None:
    try:
        config = get_config_manager()
        if config and hasattr(config, "sender_strategies"):
            strategies = config.sender_strategies
            return SenderStrategySettings(
                telegram=bool(getattr(strategies, "telegram", True)),
                aiocqhttp=bool(getattr(strategies, "aiocqhttp", True)),
                qq_official=bool(getattr(strategies, "qq_official", True)),
                weixin_oc=bool(getattr(strategies, "weixin_oc", True)),
            )
    except Exception:
        return None
    return None


def _sender_disabled_by_strategy(
    normalized: str,
    strategies: SenderStrategySettings | None,
) -> bool:
    if strategies is None:
        return False
    if normalized in {"telegram", "tg"}:
        return not strategies.telegram
    if normalized in {"aiocqhttp", "onebot", "onebot11", "onebotv11"}:
        return not strategies.aiocqhttp
    if normalized in {"qq_official", "qqofficial", "qq"}:
        return not strategies.qq_official
    if normalized in {"wechat", "weixin", "weixin_oc"}:
        return not strategies.weixin_oc
    return False


def get_sender_for_platform(
    platform_name: str | None,
    *,
    sender_strategies: SenderStrategySettings | None = None,
) -> type[DefaultMessageSender]:
    """根据平台类型获取消息发送器

    Args:
        platform_name: 平台类型名称，如 "telegram", "aiocqhttp" 等

    Returns:
        对应的消息发送器类
    """
    if not platform_name:
        return DefaultMessageSender

    normalized = platform_name.strip().lower()

    strategies = sender_strategies or _get_legacy_sender_strategies()
    if _sender_disabled_by_strategy(normalized, strategies):
        logger.debug("Sender disabled by strategy config: %s", platform_name)
        return DefaultMessageSender

    # 查找对应的发送器
    sender_class = _SENDER_MAP.get(normalized)
    if sender_class:
        logger.debug(
            "Found sender for platform '%s': %s", platform_name, sender_class.__name__
        )
        return sender_class

    # 尝试模糊匹配
    for key, sender_cls in _SENDER_MAP.items():
        if key in normalized:
            logger.debug(
                "Fuzzy matched sender for '%s': %s", platform_name, sender_cls.__name__
            )
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
    logger.info(
        "Registered custom sender for platform '%s': %s",
        platform,
        sender_class.__name__,
    )
