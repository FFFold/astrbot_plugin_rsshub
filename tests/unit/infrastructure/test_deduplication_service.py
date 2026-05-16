"""当前去重服务单元测试."""

from __future__ import annotations

from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub.src.domain.services.content_filter import (
    ContentFilterService,
)


class TestContentFilterService:
    """ContentFilterService 测试类."""

    def test_new_feed_entry_is_not_duplicate(self):
        feed = Feed(link="https://example.com/rss.xml")
        service = ContentFilterService()

        assert service.is_duplicate(feed, "guid-1") is False

    def test_recorded_entry_is_duplicate(self):
        feed = Feed(link="https://example.com/rss.xml")
        service = ContentFilterService()

        service.record_entry(feed, "guid-1")

        assert service.is_duplicate(feed, "guid-1") is True
        assert feed.entry_hashes == [["guid-1"]]

    def test_duplicate_searches_all_hash_groups(self):
        feed = Feed(
            link="https://example.com/rss.xml",
            entry_hashes=[
                ["guid-1", "link:https://example.com/1"],
                ["guid-2", "link:https://example.com/2"],
            ],
        )
        service = ContentFilterService()

        assert service.is_duplicate(feed, "link:https://example.com/2") is True
        assert service.is_duplicate(feed, "guid-3") is False
