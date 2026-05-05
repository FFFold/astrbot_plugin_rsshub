"""测试 HTML 清理器"""

from __future__ import annotations

import pytest

from astrbot_plugin_rsshub.src.infrastructure.utils import HTMLCleaner, clean_html


class TestHTMLCleaner:
    """测试 HTMLCleaner 类"""

    def test_clean_removes_script_tags(self):
        """测试清除 script 标签"""
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = HTMLCleaner.clean(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_clean_removes_style_tags(self):
        """测试清除 style 标签"""
        html = '<style>body{color:red}</style><p>Text</p>'
        result = HTMLCleaner.clean(html)
        assert "<style>" not in result
        assert "Text" in result

    def test_clean_allows_common_tags(self):
        """测试保留常用标签"""
        html = '<p>Paragraph</p><br/><b>Bold</b><i>Italic</i><a href="link">Link</a>'
        result = HTMLCleaner.clean(html)
        assert "<p>" in result
        assert "<br/>" in result or "<br>" in result
        assert "<b>" in result or "<strong>" in result
        assert "<i>" in result or "<em>" in result

    def test_clean_truncates_long_text(self):
        """测试截断长文本"""
        html = "A" * 1000
        result = HTMLCleaner.clean(html, length_limit=100)
        assert len(result) <= 110  # 允许一些额外空间用于截断标记
        assert "..." in result

    def test_clean_no_truncation_when_under_limit(self):
        """测试短文本不截断"""
        html = "Short text"
        result = HTMLCleaner.clean(html, length_limit=100)
        assert "Short text" in result
        assert "..." not in result

    def test_clean_empty_string(self):
        """测试空字符串"""
        result = HTMLCleaner.clean("")
        assert result == ""

    def test_clean_none(self):
        """测试 None 输入"""
        result = HTMLCleaner.clean(None)
        assert result == ""

    def test_strip_removes_all_tags(self):
        """测试 strip 移除所有标签"""
        html = '<p>Hello <b>World</b></p>'
        result = HTMLCleaner.strip(html)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strip_truncates_long_text(self):
        """测试 strip 截断长文本"""
        html = "A" * 1000
        result = HTMLCleaner.strip(html, length_limit=50)
        assert len(result) <= 60
        assert "..." in result

    def test_extract_text_from_links(self):
        """测试从链接中提取文本"""
        html = '<a href="http://example.com">Click here</a>'
        result = HTMLCleaner.extract_text(html)
        assert "Click here" in result
        assert "<a" not in result

    def test_extract_text_removes_tags(self):
        """测试 extract_text 移除标签"""
        html = '<p>Hello <b>World</b></p>'
        result = HTMLCleaner.extract_text(html)
        assert "Hello" in result
        assert "World" in result
        assert "<" not in result


class TestCleanHtmlFunction:
    """测试 clean_html 便捷函数"""

    def test_clean_html_basic(self):
        """测试基本清理"""
        html = '<p>Hello</p><script>alert(1)</script>'
        result = clean_html(html)
        assert "<p>" in result
        assert "<script>" not in result
