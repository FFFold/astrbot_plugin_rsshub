"""消息格式化器基础

提供 RSS 消息格式化的基础功能。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ...utils import get_logger

logger = get_logger()


@dataclass
class FormattedMessage:
    """格式化后的消息"""

    text: str
    media: list[tuple[str, str]] = None  # [(type, url), ...]
    buttons: list[dict] = None  # 平台特定的按钮
    metadata: dict = None  # 额外元数据

    def __post_init__(self):
        if self.media is None:
            self.media = []
        if self.buttons is None:
            self.buttons = []
        if self.metadata is None:
            self.metadata = {}


class BaseMessageFormatter(ABC):
    """消息格式化器基类

    所有消息格式化器必须继承此类。
    """

    def __init__(self, **options) -> None:
        """初始化格式化器

        Args:
            **options: 格式化选项
        """
        self.options = options

    @abstractmethod
    def format_entry(
        self,
        entry: dict[str, Any],
        feed_title: str = "",
        feed_link: str = "",
    ) -> FormattedMessage:
        """格式化单个 RSS 条目

        Args:
            entry: RSS 条目数据
            feed_title: Feed 标题
            feed_link: Feed 链接

        Returns:
            格式化后的消息
        """
        pass

    @abstractmethod
    def format_entries(
        self,
        entries: list[dict[str, Any]],
        feed_title: str = "",
        feed_link: str = "",
    ) -> list[FormattedMessage]:
        """格式化多个 RSS 条目

        Args:
            entries: RSS 条目列表
            feed_title: Feed 标题
            feed_link: Feed 链接

        Returns:
            格式化后的消息列表
        """
        pass

    def _escape_html(self, text: str) -> str:
        """转义 HTML 特殊字符"""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _strip_html_tags(self, html: str) -> str:
        """移除 HTML 标签"""
        import re
        if not html:
            return ""
        # 简单的 HTML 标签移除
        text = re.sub(r"<[^>]+>", "", html)
        # 解码 HTML 实体
        import html
        text = html.unescape(text)
        return text.strip()
