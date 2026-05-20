"""Agent XML entry push service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from xml.etree import ElementTree

from ...infrastructure.utils import get_logger
from .feed_polling_service import FeedPollingService
from .html_parser import HTMLParser
from .notification_dispatcher import (
    SendTarget,
    build_agent_entry_guid,
    normalize_media_items,
)

logger = get_logger()

MAX_XML_BYTES = 256 * 1024
MAX_XML_NODES = 4096
FORBIDDEN_XML_TOKENS = ("<!DOCTYPE", "<!ENTITY")


class AgentXmlValidationError(ValueError):
    """Raised when agent XML input is invalid."""


@dataclass(frozen=True, slots=True)
class ParsedAgentXmlEntry:
    """Normalized agent XML payload ready for dispatch."""

    title: str
    content: str
    entry_link: str
    feed_title: str
    feed_link: str
    author: str
    entry_guid: str
    media_urls: list[str]
    media_items: list[tuple[str, str]]


def _validate_xml_input(xml: str) -> str:
    normalized = str(xml or "").strip()
    if not normalized:
        raise AgentXmlValidationError("xml 不能为空")
    if len(normalized.encode("utf-8")) > MAX_XML_BYTES:
        raise AgentXmlValidationError("xml 过大，超过 256 KiB 限制")

    upper_xml = normalized.upper()
    if any(token in upper_xml for token in FORBIDDEN_XML_TOKENS):
        raise AgentXmlValidationError("xml 不允许包含 DOCTYPE 或 ENTITY 声明")

    return normalized


def _serialize_xml_body(root: ElementTree.Element) -> str:
    parts: list[str] = []
    if root.text and root.text.strip():
        parts.append(root.text)
    for child in list(root):
        parts.append(ElementTree.tostring(child, encoding="unicode"))
        if child.tail and child.tail.strip():
            parts.append(child.tail)
    return "".join(parts).strip()


def _collect_xml_media(root: ElementTree.Element) -> list[str]:
    media_urls: list[str] = []
    for elem in root.iter():
        for attr_name in ("src", "href", "url"):
            value = str(elem.attrib.get(attr_name, "") or "").strip()
            if value.startswith(("http://", "https://")):
                media_urls.append(value)
    return list(dict.fromkeys(media_urls))


def _parse_xml_root(xml: str) -> tuple[ElementTree.Element, str]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise AgentXmlValidationError(f"xml 格式错误: {exc}") from exc

    node_count = sum(1 for _ in root.iter())
    if node_count > MAX_XML_NODES:
        raise AgentXmlValidationError("xml 节点过多，超过安全限制")

    body_xml = _serialize_xml_body(root)
    if not body_xml:
        body_xml = ElementTree.tostring(root, encoding="unicode")
    return root, body_xml


class AgentXmlPushService:
    """Validate, normalize and dispatch one XML entry for the current agent user."""

    def __init__(self, notification_dispatcher):
        self._notification_dispatcher = notification_dispatcher

    async def push_entry(
        self,
        *,
        user_id: str,
        platform_name: str | None,
        target_session: str,
        source_key: str,
        title: str,
        xml: str,
        link: str = "",
        author: str = "",
        feed_title: str = "",
        entry_guid: str = "",
        idempotency_key: str = "",
        dry_run: bool = False,
    ) -> dict[str, object]:
        source_key = str(source_key or "").strip()
        if not source_key:
            raise AgentXmlValidationError("source_key 不能为空")

        title = str(title or "").strip()
        if not title:
            raise AgentXmlValidationError("title 不能为空")

        target_session = str(target_session or "").strip()
        if not target_session:
            raise AgentXmlValidationError("当前会话为空，无法推送")

        valid_xml = _validate_xml_input(xml)
        root, body_xml = _parse_xml_root(valid_xml)
        parsed = await HTMLParser(body_xml, feed_link=link or "").parse()
        plain_body = FeedPollingService._remove_media_placeholders(
            parsed.html_tree.get_plain().strip()
        )
        content = FeedPollingService._format_dispatch_content(
            title=title,
            body=plain_body,
            link=str(link or "").strip(),
            feed_title=str(feed_title or "").strip(),
            feed_link=str(link or "").strip(),
            author=str(author or "").strip(),
        )
        media_items = FeedPollingService._media_items_from_parsed(parsed.media)
        media_urls = [
            url for _media_type, url in normalize_media_items(media_items=media_items)
        ]
        extra_media = _collect_xml_media(root)
        media_urls.extend(extra_media)
        media_urls = list(dict.fromkeys(media_urls))
        normalized_media_items = normalize_media_items(
            media_urls=media_urls,
            media_items=media_items,
        )
        final_guid = (
            str(entry_guid or "").strip()
            or str(idempotency_key or "").strip()
            or build_agent_entry_guid(
                source_key=source_key,
                user_id=user_id,
                target_session=target_session,
                title=title,
                link=str(link or "").strip(),
                xml=valid_xml,
                media_items=normalized_media_items,
            )
        )

        preview = ParsedAgentXmlEntry(
            title=title,
            content=content,
            entry_link=str(link or "").strip(),
            feed_title=str(feed_title or "").strip(),
            feed_link=str(link or "").strip(),
            author=str(author or "").strip(),
            entry_guid=final_guid,
            media_urls=media_urls,
            media_items=normalized_media_items,
        )
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "preview": {
                    "title": preview.title,
                    "content": preview.content,
                    "entry_link": preview.entry_link,
                    "feed_title": preview.feed_title,
                    "author": preview.author,
                    "entry_guid": preview.entry_guid,
                    "media_urls": preview.media_urls,
                },
            }

        result = await self._notification_dispatcher.dispatch_agent_entry(
            source_key=source_key,
            target=SendTarget(
                user_id=user_id,
                platform_name=platform_name,
                target_session=target_session,
                sub_id=None,
            ),
            content=preview.content,
            raw_xml=valid_xml,
            entry_title=preview.title,
            entry_link=preview.entry_link,
            feed_title=preview.feed_title,
            feed_link=preview.feed_link,
            media_urls=preview.media_urls,
            media_items=preview.media_items,
            entry_guid=preview.entry_guid,
        )
        result["dry_run"] = False
        result["preview"] = {
            "entry_guid": preview.entry_guid,
            "media_urls": preview.media_urls,
        }
        return result

    async def push_entry_json(
        self,
        **kwargs,
    ) -> str:
        """JSON wrapper for LLM tool output."""
        result = await self.push_entry(**kwargs)
        return json.dumps(result, ensure_ascii=False, indent=2)
