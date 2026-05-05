"""数据采集层

提供通用 HTTP 抓取和 RSS 数据源处理能力。
"""

from ...application.dto import WebFeed
from .http import HttpFetcher
from .rss import (
    Enclosure,
    EntryParsed,
    FeedDiscoverer,
    FeedDiscoveryResult,
    RSSFeedFetcher,
    RSSParser,
)

# 向后兼容：保持旧路径引用有效
from ..fetcher.rss import (
    Enclosure as _EnclosureAlias,
    EntryParsed as _EntryParsedAlias,
    FeedDiscoverer as _FeedDiscovererAlias,
    FeedDiscoveryResult as _FeedDiscoveryResultAlias,
    RSSFeedFetcher as _RSSFeedFetcherAlias,
    RSSParser as _RSSParserAlias,
)

__all__ = [
    "HttpFetcher",
    "RSSFeedFetcher",
    "RSSParser",
    "EntryParsed",
    "Enclosure",
    "FeedDiscoverer",
    "FeedDiscoveryResult",
]
