"""翻译提供者模块"""

from .baidu_translate import BaiduTranslator
from .base import BaseTranslator
from .google_translate import GoogleTranslator

__all__ = [
    "BaseTranslator",
    "GoogleTranslator",
    "BaiduTranslator",
]
