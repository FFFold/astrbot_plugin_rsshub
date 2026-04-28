"""RSS Feed 抓取器

提供 RSS/Atom 内容的异步抓取和解析功能。
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from ssl import SSLError
from typing import Final

import aiohttp
import feedparser

from ...application.dto import WebFeed
from ...domain.exceptions import WebError
from ..utils import get_logger

logger = get_logger()

FEED_ACCEPT: Final = (
    "application/rss+xml, application/rdf+xml, application/atom+xml, "
    "application/xml;q=0.9, text/xml;q=0.8, text/*;q=0.7, application/*;q=0.6"
)


class RSSFeedFetcher:
    """RSS Feed 异步抓取器，管理共享 aiohttp session。"""

    def __init__(self, timeout: int = 30, proxy: str = "") -> None:
        self.timeout = max(1, int(timeout or 30))
        self.proxy = (proxy or "").strip()
        self._session: aiohttp.ClientSession | None = None
        self._session_lock: asyncio.Lock | None = None

    async def close(self) -> None:
        """关闭内部管理的 session。"""
        if self._session_lock is None:
            return
        async with self._session_lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
            self._session = None

    async def _get_shared_session(self) -> aiohttp.ClientSession:
        if self._session_lock is None:
            self._session_lock = asyncio.Lock()
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self._session

    async def fetch(
        self,
        url: str,
        *,
        timeout: float | None = None,
        headers: dict[str, str] | None = None,
        verbose: bool = True,
        proxy: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> WebFeed:
        """抓取 RSS/Atom 内容并解析为 ``WebFeed``。

        Args:
            url: Feed URL
            timeout: 请求超时（秒），默认使用实例配置
            headers: 额外请求头
            verbose: 是否输出详细日志
            proxy: 临时代理地址（优先于实例代理）
            session: 外部 session（若提供则直接使用）

        Returns:
            WebFeed 抓取结果对象
        """
        ret = WebFeed(url=url, ori_url=url)
        log_level = 30 if verbose else 10
        effective_proxy = (proxy or "").strip() or self.proxy

        _headers: dict[str, str] = {}
        if headers:
            _headers.update(headers)
        if "Accept" not in _headers:
            _headers["Accept"] = FEED_ACCEPT

        use_shared = not effective_proxy and session is None
        client: aiohttp.ClientSession
        temp_session: aiohttp.ClientSession | None = None

        try:
            if use_shared:
                client = await self._get_shared_session()
            elif session is not None:
                client = session
            else:
                temp_session = aiohttp.ClientSession(proxy=effective_proxy or None)
                client = temp_session

            async with client.get(
                url,
                headers=_headers,
                timeout=timeout or self.timeout,
                proxy=effective_proxy or None if not use_shared else None,
            ) as resp:
                rss_content = await resp.read()
                ret.content = rss_content
                ret.url = str(resp.url)
                ret.headers = dict(resp.headers.items())
                ret.status = resp.status
                ret.reason = resp.reason

                etag_header = ret.etag
                if etag_header:
                    logger.debug(
                        "feed_get: Received ETag '%s' for %s", etag_header, url
                    )

                if (
                    resp.status == 200
                    and int(resp.headers.get("Content-Length", "1")) == 0
                ):
                    ret.status = 304
                    return ret

                if resp.status == 304:
                    return ret

                if rss_content is None or resp.status != 200:
                    status_caption = f"{resp.status}" + (
                        f" {resp.reason}" if resp.reason else ""
                    )
                    ret.error = WebError(
                        error_name="status error",
                        status=status_caption,
                        url=url,
                        log_level=log_level,
                    )
                    return ret

                with BytesIO(rss_content) as rss_content_io:
                    rss_d = feedparser.parse(rss_content_io, sanitize_html=False)

                if not rss_d.feed.get("title"):
                    if not rss_d.entries and (
                        rss_d.bozo
                        or not (rss_d.feed.get("link") or rss_d.feed.get("updated"))
                    ):
                        ret.error = WebError(
                            error_name="feed invalid",
                            url=ret.url,
                            log_level=log_level,
                        )
                        return ret
                    rss_d.feed["title"] = ret.url

                ret.rss_d = rss_d

        except aiohttp.InvalidURL:
            ret.error = WebError(error_name="URL invalid", url=url, log_level=log_level)
        except (
            asyncio.TimeoutError,
            aiohttp.ClientError,
            SSLError,
            OSError,
            ConnectionError,
            TimeoutError,
        ) as e:
            ret.error = WebError(
                error_name="network error",
                url=url,
                base_error=e,
                log_level=log_level,
            )
        except Exception as e:
            ret.error = WebError(
                error_name="internal error",
                url=url,
                base_error=e,
                log_level=40,
            )
        finally:
            if temp_session is not None and not temp_session.closed:
                await temp_session.close()

        return ret
