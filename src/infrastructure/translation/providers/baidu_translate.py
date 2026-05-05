"""Baidu 翻译提供者"""

from __future__ import annotations

import hashlib
import random
from typing import TYPE_CHECKING

import aiohttp

from ...utils import get_logger
from .base import BaseTranslator

logger = get_logger()


class BaiduTranslator(BaseTranslator):
    """Baidu 翻译提供者（使用百度翻译API）"""

    NAME = "baidu"
    LANG_MAP = {
        "zh-CN": "zh",
        "zh-TW": "cht",
        "en": "en",
        "ja": "jp",
        "ko": "kor",
        "fr": "fra",
        "de": "de",
        "es": "spa",
        "ru": "ru",
        "ar": "ara",
        "pt": "pt",
        "it": "it",
    }

    def __init__(self, session: "aiohttp.ClientSession | None" = None):
        super().__init__(session)
        self._app_id: str | None = None
        self._secret_key: str | None = None

    def _load_credentials(self) -> bool:
        """从配置加载百度API凭证"""
        try:
            from ...config import get_config_manager

            config = get_config_manager()
            if config and hasattr(config, "baidu_translate"):
                baidu_config = config.baidu_translate
                self._app_id = getattr(baidu_config, "app_id", None)
                self._secret_key = getattr(baidu_config, "secret_key", None)
                return bool(self._app_id and self._secret_key)
        except Exception:
            pass
        return False

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return self._load_credentials()

    def _generate_sign(self, text: str, salt: int) -> str:
        """生成百度API签名"""
        if not self._app_id or not self._secret_key:
            return ""
        sign_str = f"{self._app_id}{text}{salt}{self._secret_key}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str | None:
        """使用百度翻译API翻译文本"""
        if not text or not text.strip():
            return text

        if not self._load_credentials():
            logger.warning("Baidu翻译: 未配置API凭证")
            return None

        try:
            salt = random.randint(32768, 65536)
            sign = self._generate_sign(text, salt)

            params = {
                "q": text,
                "from": self._normalize_lang(source_lang) if source_lang else "auto",
                "to": self._normalize_lang(target_lang),
                "appid": self._app_id,
                "salt": salt,
                "sign": sign,
            }

            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"

            session = self._session or aiohttp.ClientSession()
            try:
                async with session.get(url, params=params) as response:
                    data = await response.json()
            finally:
                if not self._session:
                    await session.close()

            if "error_code" in data:
                logger.warning(f"Baidu翻译API错误: {data}")
                return None

            if "trans_result" in data and data["trans_result"]:
                return data["trans_result"][0].get("dst", text)

        except Exception as e:
            logger.warning(f"Baidu翻译失败: {e}")

        return None

    async def detect_language(self, text: str) -> str | None:
        """检测文本语言（百度API自动检测）"""
        return None
