"""测试 RSS 解析器"""

from __future__ import annotations

from pathlib import Path

from astrbot_plugin_rsshub.src.infrastructure.fetcher import EntryParsed, RSSParser
from astrbot_plugin_rsshub.src.infrastructure.utils import get_lock_manager
from feedparser import FeedParserDict


class TestRSSParser:
    """测试 RSSParser 类"""

    def setup_method(self):
        """每个测试前清理锁管理器"""
        # 清理锁管理器状态
        manager = get_lock_manager()
        manager._feed_locks.clear()
        manager._user_locks.clear()
        manager._hostname_locks.clear()

    def test_parse_simple_rss(self, sample_rss_feed):
        """测试解析简单 RSS"""
        parser = RSSParser()
        entries, error = parser.parse(sample_rss_feed)

        assert error is None
        assert len(entries) == 3

        # 验证第一个条目
        entry = entries[0]
        assert entry.title == "Test Article 1"
        assert entry.link == "https://example.com/article1"
        assert entry.id == "https://example.com/article1"
        assert entry.published is not None
        assert "<title>Test Article 1</title>" in entry.raw_xml
        assert entry.raw_xml.startswith("<item>")
        assert "<title>Test Article 1</title>" in entry.raw_xml
        assert "<link>https://example.com/article1</link>" in entry.raw_xml

    def test_parse_atom_feed(self, sample_atom_feed):
        """测试解析 Atom feed"""
        parser = RSSParser()
        entries, error = parser.parse(sample_atom_feed)

        assert error is None
        assert len(entries) == 2

        entry = entries[0]
        assert entry.title == "Atom Entry 1"
        assert entry.link == "https://example.com/entry1"
        assert "entry" in entry.raw_xml.split(">", 1)[0]
        assert "Atom Entry 1" in entry.raw_xml

    def test_parse_with_media(self, sample_media_feed):
        """测试解析带媒体的 RSS"""
        parser = RSSParser()
        entries, error = parser.parse(sample_media_feed)

        assert error is None
        assert len(entries) == 3

        # 第一个条目应该有媒体
        entry1 = entries[0]
        assert len(entry1.enclosures) >= 1
        assert entry1.enclosures[0].url == "https://example.com/image1.jpg"

    def test_parse_content_encoded_from_juya_ai_daily_fixture(self, fixtures_dir: Path):
        """测试解析 content:encoded 中的完整正文。"""
        xml = (fixtures_dir / "feeds" / "juya_ai_daily_minimal.xml").read_text(
            encoding="utf-8"
        )

        parser = RSSParser()
        entries, error = parser.parse(xml)

        assert error is None
        assert len(entries) == 1
        entry = entries[0]
        assert entry.summary.startswith("AI 早报 2026-05-19")
        assert "<h1>AI 早报 2026-05-19</h1>" in entry.content
        assert "Qwen3.7 Max Preview" in entry.content
        assert len(entry.content) > len(entry.summary)

    def test_parse_entry_reads_feedparser_content_encoded_compat_field(self):
        """测试 feedparser 兼容字段 content_encoded 也能作为正文。"""
        entry = FeedParserDict(
            {
                "title": "compat",
                "link": "https://example.com/compat",
                "summary": "short summary",
                "content_encoded": "<p>full compat content</p>",
            }
        )

        parsed = RSSParser.parse_entry(entry)

        assert parsed.content == "<p>full compat content</p>"
        assert parsed.summary == "short summary"

    def test_parse_invalid_xml(self):
        """测试解析无效 XML"""
        parser = RSSParser()
        entries, error = parser.parse("not valid xml")

        assert error is not None
        assert len(entries) == 0

    def test_parse_empty_string(self):
        """测试解析空字符串"""
        parser = RSSParser()
        entries, error = parser.parse("")

        assert error is not None
        assert len(entries) == 0


class TestEntryParsed:
    """测试 EntryParsed 类"""

    def test_entry_to_dict(self):
        """测试条目转换为字典"""
        entry = EntryParsed(
            id="entry-001",
            title="Test Entry",
            link="https://example.com/entry",
            summary="Test summary",
            content="Full content",
            author="Test Author",
            enclosures=[],
            published=None,
            tags=["tag1", "tag2"],
        )

        data = entry.to_dict()
        assert data["id"] == "entry-001"
        assert data["title"] == "Test Entry"
        assert data["link"] == "https://example.com/entry"
        assert data["tags"] == ["tag1", "tag2"]

    def test_entry_text_content(self):
        """测试条目文本内容"""
        entry = EntryParsed(
            id="entry-001",
            title="Test Entry",
            link="https://example.com/entry",
            summary="Summary text",
            content="Full content text",
            author=None,
            enclosures=[],
            published=None,
            tags=[],
        )

        # 优先使用 content
        text = entry.text_content()
        assert "Full content text" in text

    def test_entry_text_content_fallback_to_summary(self):
        """测试文本内容回退到 summary"""
        entry = EntryParsed(
            id="entry-001",
            title="Test Entry",
            link="https://example.com/entry",
            summary="Summary text",
            content=None,
            author=None,
            enclosures=[],
            published=None,
            tags=[],
        )

        text = entry.text_content()
        assert "Summary text" in text
