"""RSS 服务包（兼容别名）

此包已迁移至 ``fetcher/``，保留此文件仅用于向后兼容。
请优先引用 ``from ...infrastructure.fetcher import ...``。
"""

from ...application.dto import WebFeed
from ..fetcher.rss import (
    Enclosure,
    EntryParsed,
    FeedDiscoverer,
    FeedDiscoveryResult,
    RSSFeedFetcher,
    RSSParser,
)

__all__ = [
    "WebFeed",
    "RSSFeedFetcher",
    "RSSParser",
    "EntryParsed",
    "Enclosure",
    "FeedDiscoverer",
    "FeedDiscoveryResult",
]
