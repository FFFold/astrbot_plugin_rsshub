"""RSStT 样式消息格式化器

RSStT (RSS to Telegram Bot) 默认样式。
"""

from __future__ import annotations

from typing import Any

from ...utils import get_logger
from .base_formatter import BaseMessageFormatter, FormattedMessage

logger = get_logger()


class RSStTMessageFormatter(BaseMessageFormatter):
    """RSStT 样式消息格式化器

    默认的 RSS 消息格式，特点：
    - 标题突出显示
    - 包含链接
    - 支持摘要
    - 显示作者和来源

    格式示例：
        **标题**
        摘要内容...
        链接: https://example.com
        作者: Author Name
    """

    def __init__(
        self,
        **options,
    ) -> None:
        """初始化 RSStT 格式化器

        Args:
            **options: 格式化选项
                - show_title: 是否显示标题 (默认: True)
                - show_link: 是否显示链接 (默认: True)
                - show_author: 是否显示作者 (默认: True)
                - show_via: 是否显示来源 (默认: True)
                - length_limit: 长度限制 (默认: 0 无限制)
                - style: 0=RSStT, 1=flowerss
        """
        super().__init__(**options)
        self.show_title = options.get("show_title", True)
        self.show_link = options.get("show_link", True)
        self.show_author = options.get("show_author", True)
        self.show_via = options.get("show_via", True)
        self.length_limit = options.get("length_limit", 0)

    def format_entry(
        self,
        entry: dict[str, Any],
        feed_title: str = "",
        feed_link: str = "",
    ) -> FormattedMessage:
        """格式化单个条目为 RSStT 样式"""
        lines = []

        # 标题
        title = entry.get("title", "")
        if self.show_title and title:
            lines.append(f"**{self._escape_html(title)}**")

        # 摘要/内容
        summary = entry.get("summary", "")
        content = entry.get("content", "")
        text = content or summary
        if text:
            # 移除 HTML 标签
            plain_text = self._strip_html_tags(text)
            # 截断
            if self.length_limit > 0:
                plain_text = self._truncate_text(plain_text, self.length_limit)
            lines.append(plain_text)

        # 链接
        link = entry.get("link", "")
        if self.show_link and link:
            lines.append(f"链接: {link}")

        # 作者
        author = entry.get("author", "")
        if self.show_author and author:
            lines.append(f"作者: {author}")

        # 来源
        if self.show_via and feed_title:
            lines.append(f"来源: {feed_title}")

        # 媒体
        media = []
        enclosures = entry.get("enclosures", [])
        for enc in enclosures:
            enc_type = enc.get("type", "")
            enc_url = enc.get("href", "")
            if enc_type.startswith("image/"):
                media.append(("image", enc_url))
            elif enc_type.startswith("video/"):
                media.append(("video", enc_url))
            elif enc_type.startswith("audio/"):
                media.append(("audio", enc_url))

        # 提取媒体链接
        media_urls = entry.get("media_urls", [])
        for url in media_urls:
            if url not in [m[1] for m in media]:
                # 根据扩展名判断类型
                if any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]):
                    media.append(("image", url))
                elif any(url.endswith(ext) for ext in [".mp4", ".avi", ".mov"]):
                    media.append(("video", url))

        return FormattedMessage(
            text="\n\n".join(lines),
            media=media,
        )

    def format_entries(
        self,
        entries: list[dict[str, Any]],
        feed_title: str = "",
        feed_link: str = "",
    ) -> list[FormattedMessage]:
        """格式化多个条目"""
        return [
            self.format_entry(entry, feed_title, feed_link)
            for entry in entries
        ]
