"""翻译服务基础模块

提供翻译服务的基础接口和通用实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp


class BaseTranslator(ABC):
    """翻译提供者抽象基类

    所有翻译提供者必须继承此类并实现所需方法。
    """

    NAME: str = ""
    LANG_MAP: dict[str, str] = {}

    def __init__(self, session: "aiohttp.ClientSession | None" = None):
        self._session = session

    @abstractmethod
    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str | None:
        """翻译文本

        Args:
            text: 要翻译的文本
            target_lang: 目标语言代码
            source_lang: 源语言代码（None表示自动检测）

        Returns:
            翻译后的文本或None（失败时）
        """
        raise NotImplementedError

    @abstractmethod
    async def detect_language(self, text: str) -> str | None:
        """检测文本语言

        Args:
            text: 要检测的文本

        Returns:
            检测到的语言代码或None
        """
        raise NotImplementedError

    def _normalize_lang(self, lang_code: str) -> str:
        """将语言代码转换为提供者特定格式"""
        return self.LANG_MAP.get(lang_code, lang_code)

    def _denormalize_lang(self, provider_lang_code: str) -> str:
        """将提供者语言代码转回我们的格式"""
        for our_code, provider_code in self.LANG_MAP.items():
            if provider_code.lower() == provider_lang_code.lower():
                return our_code
        return provider_lang_code

    def is_configured(self) -> bool:
        """检查翻译器是否配置正确"""
        return True
