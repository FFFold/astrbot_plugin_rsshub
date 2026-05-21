"""Minimal Telegraph client for sender-side media diversion."""

from __future__ import annotations

import json
from html import escape
from typing import TYPE_CHECKING

import aiohttp

from ...utils import get_logger

if TYPE_CHECKING:
    from .types import ChannelInfo

logger = get_logger()


class TelegraphClient:
    """Create Telegraph pages and return the public page URL."""

    API_BASE_URL = "https://api.telegra.ph"

    def __init__(self, *, access_token: str, timeout_seconds: int = 30) -> None:
        self._access_token = str(access_token or "").strip()
        self._timeout_seconds = max(1, int(timeout_seconds or 30))

    @property
    def enabled(self) -> bool:
        return bool(self._access_token)

    async def create_media_page(
        self,
        *,
        title: str,
        content: str,
        media_urls: list[str],
        channel: ChannelInfo | None = None,
    ) -> str:
        if not self.enabled:
            raise ValueError("missing telegraph access token")

        page_title = str(title or "").strip() or "RSSHub"
        html_content = self._build_html(
            title=page_title,
            content=content,
            media_urls=media_urls,
            channel=channel,
        )
        payload = {
            "access_token": self._access_token,
            "title": page_title[:256],
            "content": json.dumps(html_content, ensure_ascii=False),
            "return_content": "false",
        }

        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.API_BASE_URL}/createPage",
                data=payload,
            ) as resp:
                data = await resp.json(content_type=None)

        if not isinstance(data, dict) or not data.get("ok"):
            raise RuntimeError(f"telegraph createPage failed: {data}")
        result = data.get("result") or {}
        url = str(result.get("url") or "").strip()
        if not url:
            raise RuntimeError("telegraph createPage returned empty url")
        return url

    @staticmethod
    def _build_html(
        *,
        title: str,
        content: str,
        media_urls: list[str],
        channel: ChannelInfo | None,
    ) -> list[dict[str, object]]:
        nodes: list[dict[str, object]] = []
        safe_title = escape(title)
        if safe_title:
            nodes.append({"tag": "h3", "children": [safe_title]})

        channel_title = escape(str(channel.title or "").strip()) if channel else ""
        channel_link = escape(str(channel.link or "").strip()) if channel else ""
        if channel_title or channel_link:
            children: list[object] = []
            if channel_title:
                children.append(channel_title)
            if channel_link:
                if children:
                    children.append(" | ")
                children.append(
                    {
                        "tag": "a",
                        "attrs": {"href": channel_link},
                        "children": [channel_link],
                    }
                )
            nodes.append({"tag": "p", "children": children})

        for paragraph in [part.strip() for part in str(content or "").split("\n\n")]:
            if paragraph:
                nodes.append({"tag": "p", "children": [escape(paragraph)]})

        for media_url in media_urls:
            safe_url = escape(media_url)
            nodes.append(
                {
                    "tag": "p",
                    "children": [
                        {
                            "tag": "a",
                            "attrs": {"href": safe_url},
                            "children": [safe_url],
                        }
                    ],
                }
            )
        return nodes
