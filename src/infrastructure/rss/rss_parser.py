"""RSS 条目解析模块

提供 RSS/Atom 条目解析和标准化处理功能。
"""

from __future__ import annotations

import html
import math
import numbers
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel, Field


class Enclosure(BaseModel):
    """附件信息"""

    url: str = Field(..., description="附件URL")
    length: int = Field(default=0, description="文件大小")
    type: str = Field(default="", description="MIME类型")


class EntryParsed(BaseModel):
    """解析后的 RSS 条目"""

    title: str = Field(default="", description="标题")
    link: str = Field(default="", description="链接")
    author: str = Field(default="", description="作者")
    content: str = Field(default="", description="正文内容")
    summary: str = Field(default="", description="摘要")
    guid: str = Field(default="", description="全局唯一标识")
    entry_id: str = Field(default="", description="条目ID")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    enclosures: list[Enclosure] = Field(default_factory=list, description="附件列表")
    published: datetime | None = Field(default=None, description="发布时间")
    updated: datetime | None = Field(default=None, description="更新时间")


class RSSParser:
    """RSS 条目解析器"""

    @staticmethod
    def parse_entry(entry: Any, feed_link: str | None = None) -> EntryParsed:
        """解析 feedparser 条目对象为结构化数据

        Args:
            entry: feedparser 条目对象
            feed_link: feed 链接（用于解析相对链接）

        Returns:
            EntryParsed 对象
        """
        result = EntryParsed()

        result.title = RSSParser._get_text(entry.get("title", ""))
        result.link = RSSParser._get_link(entry, feed_link)
        result.author = RSSParser._get_text(entry.get("author", ""))
        result.guid = RSSParser._get_text(entry.get("guid", ""))
        result.entry_id = RSSParser._get_text(entry.get("id", ""))

        content = entry.get("content", [])
        if content:
            result.content = content[0].get("value", "")

        summary = entry.get("summary") or entry.get("description")
        if summary:
            result.summary = str(summary)

        if not result.content:
            result.content = result.summary

        tags = entry.get("tags", [])
        result.tags = [tag.get("term", "") for tag in tags if tag.get("term")]

        enclosures = entry.get("enclosures", [])
        result.enclosures = [
            Enclosure(
                url=e.get("href", ""),
                length=int(e.get("length", 0)),
                type=e.get("type", ""),
            )
            for e in enclosures
            if e.get("href")
        ]

        if entry.get("published_parsed"):
            try:
                result.published = datetime(
                    *entry.published_parsed[:6], tzinfo=timezone.utc
                )
            except Exception:
                pass
        if entry.get("updated_parsed"):
            try:
                result.updated = datetime(
                    *entry.updated_parsed[:6], tzinfo=timezone.utc
                )
            except Exception:
                pass

        return result

    @staticmethod
    def _get_text(raw_html: str) -> str:
        """从 HTML 中提取纯文本"""
        text = re.sub(r"<[^>]+>", "", raw_html)
        text = html.unescape(text)
        return text.strip()

    @staticmethod
    def _get_link(entry: Any, feed_link: str | None = None) -> str:
        """获取条目链接，处理相对链接"""
        link = entry.get("link") or entry.get("guid")
        if link and not link.startswith("http"):
            if feed_link:
                link = urljoin(feed_link, link)
        return link or ""

    @staticmethod
    def normalize_text(value: str, max_length: int = 1024) -> str:
        """标准化文本：去 HTML 实体、合并空白、小写、截断"""
        text = html.unescape(value or "")
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text[:max_length]

    @staticmethod
    def normalize_identifier(value: str, max_length: int = 1024) -> str:
        """标准化标识符：保留大小写和内部空白，截断"""
        return (value or "").strip()[:max_length]

    @staticmethod
    def normalize_path(path: str) -> str:
        """标准化 URL 路径"""
        normalized = path or ""
        if normalized != "/":
            normalized = normalized.rstrip("/")
        return normalized

    @staticmethod
    def normalize_config_positive_int(raw: Any, key: str, default: int) -> int:
        """将配置值标准化为正整数"""
        if isinstance(raw, bool):
            logger = get_logger()
            logger.warning("Invalid %s=%r; expected positive integer", key, raw)
            return default

        if isinstance(raw, numbers.Integral):
            if raw > 0:
                return int(raw)
            logger.warning("Invalid %s=%r; expected positive integer", key, raw)
            return default

        if isinstance(raw, numbers.Real):
            if math.isfinite(float(raw)) and raw > 0 and float(raw).is_integer():
                coerced = int(raw)
                logger = get_logger()
                logger.info(
                    "Coerced %s=%r (non-integral type) to positive integer %d",
                    key,
                    raw,
                    coerced,
                )
                return coerced
            logger.warning(
                "Invalid %s=%r; expected positive integer "
                "(got non-integral numeric type)",
                key,
                raw,
            )
            return default

        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                return default
            if re.fullmatch(r"\d+", stripped):
                parsed = int(stripped)
                return parsed if parsed > 0 else default
            logger.warning("Invalid %s=%r; expected positive integer", key, raw)
            return default

        return default
