"""RSS 条目解析模块

提供 RSS/Atom 条目解析和结构化处理功能。
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import feedparser
from pydantic import BaseModel, Field

from ...utils import get_logger

logger = get_logger()


class Enclosure(BaseModel):
    """附件信息"""

    url: str = Field(..., description="附件URL")
    length: int = Field(default=0, description="文件大小")
    type: str = Field(default="", description="MIME类型")


class EntryParsed(BaseModel):
    """解析后的 RSS 条目"""

    id: str = Field(default="", description="条目稳定标识")
    title: str = Field(default="", description="标题")
    link: str = Field(default="", description="链接")
    author: str | None = Field(default="", description="作者")
    content: str | None = Field(default="", description="正文内容")
    summary: str | None = Field(default="", description="摘要")
    guid: str = Field(default="", description="全局唯一标识")
    entry_id: str = Field(default="", description="条目ID")
    raw_xml: str = Field(default="", description="原始 item/entry XML")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    enclosures: list[Enclosure] = Field(default_factory=list, description="附件列表")
    published: datetime | None = Field(default=None, description="发布时间")
    updated: datetime | None = Field(default=None, description="更新时间")

    def to_dict(self) -> dict[str, Any]:
        """转换为普通字典，保留历史测试依赖的字段名。"""
        return self.model_dump()

    def text_content(self) -> str:
        """获取用于搜索/格式化的条目文本内容。"""
        parts = [
            self.title or "",
            self.content or self.summary or "",
        ]
        return "\n".join(part for part in parts if part)


class RSSParser:
    """RSS 条目解析器"""

    def parse(self, xml_content: str | bytes) -> tuple[list[EntryParsed], str | None]:
        """解析 RSS/Atom XML 内容为条目列表。

        Args:
            xml_content: RSS/Atom XML 文本或字节

        Returns:
            (条目列表, 错误信息) 元组。解析成功时错误信息为 None。
        """
        if not xml_content:
            return [], "RSS content is empty"

        try:
            parsed = feedparser.parse(xml_content, sanitize_html=False)
        except Exception as exc:
            return [], f"RSS parse failed: {exc}"

        entries = list(getattr(parsed, "entries", []) or [])
        feed = getattr(parsed, "feed", {}) or {}
        feed_link = feed.get("link") if hasattr(feed, "get") else None

        if not entries:
            bozo_exception = getattr(parsed, "bozo_exception", None)
            if bozo_exception:
                return [], f"RSS parse failed: {bozo_exception}"
            return [], "RSS feed has no entries"

        if getattr(parsed, "bozo", False):
            bozo_exception = getattr(parsed, "bozo_exception", None)
            if bozo_exception and not feed:
                return [], f"RSS parse failed: {bozo_exception}"

        parsed_entries = [self.parse_entry(entry, feed_link=feed_link) for entry in entries]
        self._attach_raw_xml(parsed_entries, xml_content)
        return parsed_entries, None

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
        result.id = result.entry_id or result.guid or result.link

        result.content = RSSParser._get_entry_content(entry)

        summary = entry.get("summary") or entry.get("description")
        if summary:
            result.summary = str(summary)

        if not result.content:
            result.content = result.summary

        tags = entry.get("tags", [])
        result.tags = [tag.get("term", "") for tag in tags if tag.get("term")]

        enclosures = list(entry.get("enclosures", []) or [])
        enclosures.extend(entry.get("media_content", []) or [])
        result.enclosures = [
            Enclosure(
                url=e.get("href") or e.get("url") or "",
                length=int(e.get("length", 0)),
                type=e.get("type", ""),
            )
            for e in enclosures
            if e.get("href") or e.get("url")
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
    def _get_entry_content(entry: Any) -> str:
        """获取条目正文，优先使用 feedparser 解析出的完整内容字段。"""
        content = entry.get("content", [])
        if isinstance(content, list):
            for item in content:
                value = item.get("value") if hasattr(item, "get") else None
                if value:
                    return str(value)
        elif hasattr(content, "get"):
            value = content.get("value")
            if value:
                return str(value)
        elif content:
            return str(content)

        for key in ("content_encoded", "content:encoded"):
            value = entry.get(key)
            if value:
                return str(value)

        return ""

    @staticmethod
    def _get_link(entry: Any, feed_link: str | None = None) -> str:
        """获取条目链接，处理相对链接"""
        link = entry.get("link") or entry.get("guid")
        if link and not link.startswith("http"):
            if feed_link:
                link = urljoin(feed_link, link)
        return link or ""

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        if ":" in tag:
            return tag.rsplit(":", 1)[-1]
        return tag

    @classmethod
    def _entry_xml_candidates(
        cls,
        xml_content: str | bytes,
    ) -> list[tuple[dict[str, str], str]]:
        if isinstance(xml_content, bytes):
            text = xml_content.decode("utf-8", errors="ignore")
        else:
            text = str(xml_content or "")
        if not text.strip():
            return []

        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return []

        candidates: list[tuple[dict[str, str], str]] = []
        for elem in root.iter():
            local_name = cls._local_name(elem.tag)
            if local_name not in {"item", "entry"}:
                continue
            info: dict[str, str] = {"tag": local_name}
            text_parts: list[str] = []
            for child in list(elem):
                child_name = cls._local_name(child.tag)
                child_text = "".join(child.itertext()).strip()
                if child_name in {
                    "guid",
                    "id",
                    "title",
                    "description",
                    "summary",
                    "content",
                    "author",
                    "pubDate",
                    "published",
                    "updated",
                } and child_text:
                    info[child_name] = child_text
                if child_name == "link":
                    href = str(child.attrib.get("href", "") or "").strip()
                    if href:
                        info["link"] = href
                    elif child_text:
                        info["link"] = child_text
                if child_text:
                    text_parts.append(child_text)
            info["text"] = "\n".join(text_parts)
            candidates.append((info, ElementTree.tostring(elem, encoding="unicode")))
        return candidates

    @classmethod
    def _candidate_score(cls, entry: EntryParsed, info: dict[str, str]) -> int:
        score = 0
        if entry.guid and entry.guid == info.get("guid"):
            score += 10
        if entry.entry_id and entry.entry_id == info.get("id"):
            score += 10
        if entry.link and entry.link == info.get("link"):
            score += 8
        if entry.title and entry.title == info.get("title"):
            score += 4
        summary = str(entry.summary or "").strip()
        content = str(entry.content or "").strip()
        combined = info.get("text", "")
        if summary and summary in combined:
            score += 2
        if content and content[:120] and content[:120] in combined:
            score += 2
        return score

    @classmethod
    def _attach_raw_xml(
        cls,
        entries: list[EntryParsed],
        xml_content: str | bytes,
    ) -> None:
        candidates = cls._entry_xml_candidates(xml_content)
        if not candidates:
            return

        used: set[int] = set()
        for index, entry in enumerate(entries):
            best_idx = -1
            best_score = -1
            for candidate_idx, (info, raw_xml) in enumerate(candidates):
                if candidate_idx in used:
                    continue
                score = cls._candidate_score(entry, info)
                if score > best_score:
                    best_score = score
                    best_idx = candidate_idx
            if best_idx >= 0 and best_score > 0:
                entry.raw_xml = candidates[best_idx][1]
                used.add(best_idx)
                continue
            if index < len(candidates) and index not in used:
                entry.raw_xml = candidates[index][1]
                used.add(index)
