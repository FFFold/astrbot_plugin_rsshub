"""Google 翻译提供者"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from ...utils import get_logger
from .base import BaseTranslator

if TYPE_CHECKING:
    import aiohttp

logger = get_logger()


class GoogleTranslator(BaseTranslator):
    """Google 翻译提供者（使用 Google Translate API）"""

    NAME = "google"
    LANG_MAP = {
        "zh-CN": "zh-CN",
        "zh-TW": "zh-TW",
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "ru": "ru",
        "ar": "ar",
        "pt": "pt",
        "it": "it",
    }

    def __init__(self, session: "aiohttp.ClientSession | None" = None):
        super().__init__(session)
        self._base_url = "https://translate.googleapis.com/translate_a/single"

    async def _fetch(self, url: str) -> dict | None:
        """通过 aiohttp 或临时 session 获取翻译结果"""
        import aiohttp

        if self._session:
            async with self._session.get(url) as response:
                if response.status == 200:
                    return await response.json()
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
        return None

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str | None:
        """使用 Google Translate 翻译文本"""
        if not text or not text.strip():
            return text

        try:
            params = {
                "client": "gtx",
                "sl": source_lang or "auto",
                "tl": self._normalize_lang(target_lang),
                "dt": "t",
                "q": text,
            }

            url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
            data = await self._fetch(url)

            if data and len(data) > 0 and data[0]:
                translated_parts = [part[0] for part in data[0] if part]
                return "".join(translated_parts)

        except Exception as e:
            logger.warning(f"Google翻译失败: {e}")

        return None

    async def detect_language(self, text: str) -> str | None:
        """检测文本语言"""
        if not text:
            return None

        try:
            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": "en",
                "dt": "t",
                "q": text[:100],
            }

            url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
            data = await self._fetch(url)

            if data and len(data) > 2:
                detected = data[2]
                return self._denormalize_lang(detected)

        except Exception as e:
            logger.warning(f"Google语言检测失败: {e}")

        return None
