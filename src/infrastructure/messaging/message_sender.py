"""消息发送基础设施

提供跨平台消息发送的基础设施和 DTO。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


from ..utils import get_logger

logger = get_logger()


@dataclass
class SendResult:
    """发送结果"""

    ok: bool = False
    needs_rebind: bool = False
    transient: bool = False
    http_status: int = 0
    detail: str = ""


@dataclass
class ChannelInfo:
    """频道信息"""

    title: str = ""
    link: str = ""


@dataclass
class MessageContext:
    """消息发送上下文"""

    channel: ChannelInfo = field(default_factory=ChannelInfo)
    platform_name: str = ""


class MessageSender(Protocol):
    """消息发送器协议"""

    async def send_to_user(
        self,
        session_id: str,
        content: str,
        media_items: list[tuple[str, str]] | None = None,
        prepared_media: list[Path] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """发送消息给指定用户/会话

        Args:
            session_id: 目标会话ID
            content: 消息内容
            media_items: 媒体项列表 [(类型, URL), ...]
            prepared_media: 已下载的媒体路径列表
            context: 发送上下文

        Returns:
            发送结果
        """
        ...


class BaseMessageSender:
    """消息发送器基类"""

    def __init__(self, platform_name: str) -> None:
        self.platform_name = platform_name
        self.timeout_seconds = 30
        self.proxy = ""
        self.download_media_before_send = True
        self.gif_transcode_enabled = False
        self.gif_transcode_timeout = 60
        self.video_transcode_enabled = False
        self.video_transcode_timeout = 120

    def configure_runtime(self, *, timeout_seconds: int = 30, proxy: str = "") -> None:
        """配置运行时参数"""
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.proxy = proxy or ""

    def configure_behavior(
        self,
        *,
        download_media_before_send: bool = True,
        gif_transcode_enabled: bool = False,
        gif_transcode_timeout: int = 60,
        video_transcode_enabled: bool = False,
        video_transcode_timeout: int = 120,
    ) -> None:
        """配置行为参数"""
        self.download_media_before_send = download_media_before_send
        self.gif_transcode_enabled = gif_transcode_enabled
        self.gif_transcode_timeout = max(10, gif_transcode_timeout)
        self.video_transcode_enabled = video_transcode_enabled
        self.video_transcode_timeout = max(10, video_transcode_timeout)

    @staticmethod
    def _needs_rebind_error(detail: str) -> bool:
        """判断错误是否需要重新绑定"""
        rebind_keywords = [
            "blocked",
            "chat not found",
            "user is deactivated",
            "bot was blocked",
            "bot was kicked",
            "group chat was upgraded to a supergroup",
            "the group has been migrated",
            "need administrator rights",
            "not enough rights",
        ]
        lowered = detail.lower()
        return any(kw in lowered for kw in rebind_keywords)

    @staticmethod
    def _transient_error(detail: str) -> bool:
        """判断错误是否是暂时性"""
        transient_keywords = [
            "timeout",
            "temporary",
            "retry",
            "network",
            "connection",
            "unavailable",
        ]
        lowered = detail.lower()
        return any(kw in lowered for kw in transient_keywords)


class ForwardMessageSender(BaseMessageSender):
    """转发模式消息发送器（用于 QQ）"""

    def __init__(self) -> None:
        super().__init__("aiocqhttp")

    async def send_to_user(
        self,
        session_id: str,
        content: str,
        media_items: list[tuple[str, str]] | None = None,
        prepared_media: list[Path] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """使用合并转发发送消息（待实现）"""
        # TODO: 在 Phase 5 中实现，需要 AstrBot 平台适配器
        return SendResult(ok=False, detail="Not implemented")


class DirectMessageSender(BaseMessageSender):
    """直接消息发送器（用于 Telegram 等）"""

    def __init__(self) -> None:
        super().__init__("telegram")

    async def send_to_user(
        self,
        session_id: str,
        content: str,
        media_items: list[tuple[str, str]] | None = None,
        prepared_media: list[Path] | None = None,
        context: MessageContext | None = None,
    ) -> SendResult:
        """直接发送消息（待实现）"""
        # TODO: 在 Phase 5 中实现，需要 AstrBot 平台适配器
        return SendResult(ok=False, detail="Not implemented")


def get_sender_for_platform(platform_name: str) -> type[BaseMessageSender]:
    """获取平台对应的发送器类

    Args:
        platform_name: 平台名称

    Returns:
        发送器类
    """
    platform_lower = (platform_name or "").lower()
    if "telegram" in platform_lower:
        return DirectMessageSender
    if "aiocqhttp" in platform_lower or "onebot" in platform_lower:
        return ForwardMessageSender
    return DirectMessageSender
