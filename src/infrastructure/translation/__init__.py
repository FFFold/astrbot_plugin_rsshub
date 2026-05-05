"""翻译服务模块

提供多语言翻译功能，支持Google和Baidu翻译API。
"""

from .language_detection import (
    detect_foreign_words,
    detect_language_simple,
    normalize_lang_code,
    should_translate,
)
from .providers import BaiduTranslator, BaseTranslator, GoogleTranslator
from .translation_service import TranslationService, get_available_providers, register_provider

__all__ = [
    "BaseTranslator",
    "GoogleTranslator",
    "BaiduTranslator",
    "TranslationService",
    "should_translate",
    "detect_language_simple",
    "detect_foreign_words",
    "normalize_lang_code",
    "register_provider",
    "get_available_providers",
]
