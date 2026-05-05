"""语言检测模块单元测试"""

from __future__ import annotations


from src.infrastructure.translation.language_detection import (
    calculate_target_language_ratio,
    detect_foreign_words,
    detect_language_simple,
    normalize_lang_code,
    should_translate,
)


class TestLanguageDetection:
    """语言检测测试类"""

    def test_detect_language_simple_chinese(self):
        """测试中文检测"""
        text = "这是一段中文文本，用于测试语言检测功能。"
        result = detect_language_simple(text)
        assert result == "zh-CN"

    def test_detect_language_simple_english(self):
        """测试英文检测"""
        text = "This is a sample English text for testing language detection."
        result = detect_language_simple(text)
        assert result == "en"

    def test_detect_language_simple_japanese(self):
        """测试日文检测"""
        text = "これは日本語のテキストです。"
        result = detect_language_simple(text)
        assert result == "ja"

    def test_detect_language_simple_korean(self):
        """测试韩文检测"""
        text = "이것은 한국어 텍스트입니다."
        result = detect_language_simple(text)
        assert result == "ko"

    def test_detect_language_simple_empty(self):
        """测试空文本"""
        result = detect_language_simple("")
        assert result is None

    def test_should_translate_same_language(self):
        """测试相同语言不翻译"""
        text = "这是一段中文文本"
        result = should_translate(text, "zh-CN")
        assert result is False

    def test_should_translate_different_language(self):
        """测试不同语言需要翻译"""
        text = "This is English text that should be translated to Chinese."
        result = should_translate(text, "zh-CN")
        assert result is True

    def test_should_translate_force(self):
        """测试强制翻译"""
        text = "中文"
        result = should_translate(text, "zh-CN", force_translate=True)
        assert result is True

    def test_calculate_target_language_ratio_chinese(self):
        """测试中文比例计算"""
        text = "这是一段中文文本，包含一些English单词。"
        ratio = calculate_target_language_ratio(text, "zh-CN")
        assert ratio > 0.5

    def test_calculate_target_language_ratio_english(self):
        """测试英文比例计算"""
        text = "This is mostly English text with a few 中文 characters."
        ratio = calculate_target_language_ratio(text, "en")
        assert ratio > 0.5

    def test_detect_foreign_words_non_latin_target(self):
        """测试非拉丁目标语言的外语单词检测"""
        text = "这是一段中文文本 with some English words inside it"
        ratio = detect_foreign_words(text, "zh-CN")
        assert ratio > 0

    def test_normalize_lang_code(self):
        """测试语言代码标准化"""
        assert normalize_lang_code("zh") == "zh-CN"
        assert normalize_lang_code("zh-cn") == "zh-CN"
        assert normalize_lang_code("zh_CN") == "zh-CN"
        assert normalize_lang_code("en") == "en"
        assert normalize_lang_code("ja") == "ja"
        assert normalize_lang_code("jp") == "ja"
        assert normalize_lang_code("") == "zh-CN"
