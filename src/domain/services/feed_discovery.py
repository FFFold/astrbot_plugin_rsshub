"""
Feed 自动发现服务

负责从网页 URL 中自动发现 RSS/Atom Feed 链接。
属于领域服务，因为涉及跨实体的业务逻辑。
"""

from typing import Protocol

from ..value_objects.feed_url import FeedUrl


class HttpClient(Protocol):
    """HTTP客户端接口，由基础设施层实现"""

    async def fetch_html(self, url: str) -> str:
        """获取网页HTML内容"""
        ...


class FeedDiscoveryService:
    """
    Feed 自动发现服务

    负责从网页 URL 中自动发现 RSS/Atom Feed 链接。
    """

    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    async def discover(self, page_url: str) -> list[FeedUrl]:
        """
        从网页中发现 Feed 链接

        Args:
            page_url: 网页URL

        Returns:
            发现的 FeedUrl 列表
        """
        # TODO: Phase 4 实现具体的发现逻辑
        # 1. 获取网页 HTML
        # 2. 解析 <link rel="alternate" type="application/rss+xml" ...>
        # 3. 解析 <link rel="alternate" type="application/atom+xml" ...>
        # 4. 返回 FeedUrl 列表
        return []
