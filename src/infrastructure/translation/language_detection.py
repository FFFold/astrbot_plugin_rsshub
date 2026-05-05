"""语言检测模块

提供简单的语言检测功能，用于决定是否需要翻译。
"""

from __future__ import annotations

import re
from typing import Final

# 字符范围正则表达式
CJK_CHARS: Final = re.compile(r"[\u4e00-\u9fff]")
HIRAGANA: Final = re.compile(r"[\u3040-\u309f]")
KATAKANA: Final = re.compile(r"[\u30a0-\u30ff]")
HANGUL: Final = re.compile(r"[\uac00-\ud7af]")
LATIN_CHARS: Final = re.compile(r"[a-zA-Z]")


def should_translate(
    text: str,
    target_lang: str,
    force_translate: bool = False,
) -> bool:
    """判断文本是否需要翻译

    Args:
        text: 待检测文本
        target_lang: 目标语言代码
        force_translate: 是否强制翻译

    Returns:
        是否需要翻译
    """
    if not text or not text.strip():
        return False

    if force_translate:
        return True

    text_sample = text[:500]  # 使用前500字符检测

    detected = detect_language_simple(text_sample)
    if detected is None:
        return True

    if detected == target_lang:
        return False

    # 中文变体处理
    if target_lang in ("zh-CN", "zh-TW") and detected in ("zh-CN", "zh-TW"):
        return False

    # 目标语言比例检查
    target_ratio = calculate_target_language_ratio(text_sample, target_lang)

    # 目标语言比例超过85%，不需要翻译
    if target_ratio >= 0.85:
        return False

    # 比例在50%-85%之间，检查外语单词
    if target_ratio >= 0.50:
        foreign_ratio = detect_foreign_words(text_sample, target_lang)
        if foreign_ratio < 0.10:
            return False

    return True


def detect_language_simple(text: str) -> str | None:
    """简单规则的语言检测

    Returns:
        语言代码或None
    """
    if not text or not text.strip():
        return None

    cjk_count = len(CJK_CHARS.findall(text))
    hiragana_count = len(HIRAGANA.findall(text))
    katakana_count = len(KATAKANA.findall(text))
    hangul_count = len(HANGUL.findall(text))
    latin_count = len(LATIN_CHARS.findall(text))

    clean_text = text.replace(" ", "").replace("\n", "")
    total_chars = len(clean_text)

    if total_chars == 0:
        return None

    # 日语：包含平假名或片假名
    if hiragana_count > 0 or katakana_count > 0:
        return "ja"

    # 韩语：包含韩文字符
    if hangul_count > 0:
        return "ko"

    # 中文：CJK字符超过30%
    if cjk_count > total_chars * 0.3:
        return "zh-CN"

    # 英文：拉丁字符超过50%
    if latin_count > total_chars * 0.5:
        return "en"

    return None


def calculate_target_language_ratio(text: str, target_lang: str) -> float:
    """计算文本中目标语言字符的比例

    Args:
        text: 待分析文本
        target_lang: 目标语言代码

    Returns:
        目标语言字符比例 (0.0-1.0)
    """
    if not text:
        return 0.0

    clean_text = text.replace(" ", "").replace("\n", "").replace("\t", "")
    total_chars = len(clean_text)

    if total_chars == 0:
        return 0.0

    target_count = 0

    if target_lang in ("zh-CN", "zh-TW", "zh"):
        target_count = len(CJK_CHARS.findall(clean_text))
        # 中文标点
        chinese_punct = re.findall(r'[。，、；：""' "（）《》【】？！]", clean_text)
        target_count += len(chinese_punct)
    elif target_lang in ("ja", "jp"):
        target_count = (
            len(HIRAGANA.findall(clean_text))
            + len(KATAKANA.findall(clean_text))
            + len(CJK_CHARS.findall(clean_text))
        )
    elif target_lang in ("ko", "kr"):
        target_count = len(HANGUL.findall(clean_text))
    elif target_lang == "en":
        target_count = len(LATIN_CHARS.findall(clean_text))

    return target_count / total_chars


def detect_foreign_words(text: str, target_lang: str) -> float:
    """检测文本中外语单词的比例

    Args:
        text: 待分析文本
        target_lang: 目标语言代码

    Returns:
        外语单词比例 (0.0-1.0)
    """
    if not text or target_lang == "en":
        return 0.0

    # 查找拉丁字母单词（2个字母以上）
    words = re.findall(r"[a-zA-Z]{2,}", text)
    total_words = len(words)

    if total_words == 0:
        return 0.0

    clean_text = text.replace(" ", "").replace("\n", "").replace("\t", "")
    total_chars = len(clean_text)

    if total_chars == 0:
        return 0.0

    latin_chars = len(LATIN_CHARS.findall(clean_text))

    return latin_chars / total_chars


def normalize_lang_code(lang_code: str) -> str:
    """标准化语言代码

    Args:
        lang_code: 输入语言代码

    Returns:
        标准化后的语言代码
    """
    if not lang_code:
        return "zh-CN"

    lang_map = {
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "zh_CN": "zh-CN",
        "zh-tw": "zh-TW",
        "zh_tw": "zh-TW",
        "zh-hans": "zh-CN",
        "zh-hant": "zh-TW",
        "en": "en",
        "en-us": "en",
        "en-gb": "en",
        "ja": "ja",
        "jp": "ja",
        "ko": "ko",
        "kr": "ko",
    }

    normalized = lang_code.lower().strip()
    return lang_map.get(normalized, lang_code)
