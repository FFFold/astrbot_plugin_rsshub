"""翻译服务模块

提供翻译管理、缓存和语言检测功能。
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from ...infrastructure.utils import get_logger
from .language_detection import should_translate
from .providers import BaiduTranslator, BaseTranslator, GoogleTranslator

if TYPE_CHECKING:
    import aiohttp

logger = get_logger()

# 提供者注册表
_PROVIDER_REGISTRY: dict[str, type[BaseTranslator]] = {
    "google": GoogleTranslator,
    "baidu": BaiduTranslator,
}


def register_provider(name: str, provider_class: type[BaseTranslator]) -> None:
    """注册新的翻译提供者

    Args:
        name: 提供者唯一标识
        provider_class: 继承自 BaseTranslator 的提供者类

    Raises:
        ValueError: 如果提供者名称已注册
        TypeError: 如果 provider_class 不是 BaseTranslator 的子类
    """
    if name in _PROVIDER_REGISTRY:
        raise ValueError(f"Provider '{name}' 已注册")

    if not issubclass(provider_class, BaseTranslator):
        raise TypeError(
            f"Provider 类必须继承 BaseTranslator, 得到 {provider_class.__name__}"
        )

    _PROVIDER_REGISTRY[name] = provider_class
    logger.debug(f"注册翻译提供者: {name}")


def get_available_providers() -> list[str]:
    """获取可用提供者列表"""
    return list(_PROVIDER_REGISTRY.keys())


class TranslationService:
    """翻译服务

    管理文本翻译，支持缓存和语言检测。
    使用单例模式避免重复创建实例。
    """

    SEPARATOR = "\n--【译文】--\n"
    FAILED_MARKER = "\n--【译文】--\n（翻译失败）"

    _instance: TranslationService | None = None

    def __new__(
        cls, session: aiohttp.ClientSession | None = None
    ) -> TranslationService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, session: aiohttp.ClientSession | None = None):
        if hasattr(TranslationService, "_initialized"):
            if session is not None and session != self._session:
                self._session = session
                if self._provider is not None:
                    self._provider._session = session
            return

        TranslationService._initialized = True
        self._session = session
        self._provider: BaseTranslator | None = None
        self._load_config()

    def _load_config(self) -> None:
        """从配置加载翻译设置"""
        self._target_lang = "zh-CN"
        self._force_translate = False
        self._translate_title = True
        self._translate_content = True
        self._display_original = False
        self._cache_enabled = True
        self._init_provider("google")

        try:
            from ..config import get_config_manager

            config = get_config_manager()
            if config and hasattr(config, "translation"):
                trans = config.translation
                self._target_lang = getattr(trans, "target_lang", "zh-CN")
                self._force_translate = getattr(trans, "force_translate", False)
                self._translate_title = getattr(trans, "translate_title", True)
                self._translate_content = getattr(trans, "translate_content", True)
                self._display_original = getattr(trans, "display_original", False)
                self._cache_enabled = getattr(trans, "cache_enabled", True)
                self._init_provider(getattr(trans, "provider", "google"))
        except Exception as e:
            logger.debug(f"加载翻译配置失败: {e}")

    def _init_provider(self, provider_name: str) -> None:
        """初始化翻译提供者"""
        if provider_name not in _PROVIDER_REGISTRY:
            logger.warning(f"未知翻译提供者: {provider_name}, 使用 google")
            provider_name = "google"

        provider_class = _PROVIDER_REGISTRY[provider_name]
        self._provider = provider_class(self._session)

        if not self._provider.is_configured():
            logger.warning(f"翻译提供者 '{provider_name}' 未配置")

    def _get_cache_key(self, text: str, target_lang: str) -> str:
        """生成缓存键"""
        provider_name = self._provider.NAME if self._provider else "unknown"
        key_data = f"{text}:{provider_name}:{target_lang}"
        return hashlib.md5(key_data.encode("utf-8")).hexdigest()

    async def _get_cached(self, cache_key: str) -> str | None:
        """从缓存获取翻译"""
        if not self._cache_enabled:
            return None

        try:
            from ...infrastructure.persistence import TranslationCacheORM
            from ...infrastructure.persistence.database import get_database

            db = get_database()
            async with db.get_session() as session:
                from sqlmodel import select

                stmt = select(TranslationCacheORM).where(
                    TranslationCacheORM.hash == cache_key
                )
                result = await session.execute(stmt)
                cache = result.scalar_one_or_none()
                return cache.translated_text if cache else None
        except Exception as e:
            logger.debug(f"缓存查询失败: {e}")
            return None

    async def _save_cache(self, cache_key: str, translated: str) -> None:
        """保存翻译到缓存"""
        if not self._cache_enabled:
            return

        try:
            from ...infrastructure.persistence import TranslationCacheORM
            from ...infrastructure.persistence.database import get_database

            db = get_database()
            async with db.get_session() as session:
                provider_name = self._provider.NAME if self._provider else "unknown"
                cache = TranslationCacheORM(
                    hash=cache_key,
                    provider=provider_name,
                    target_lang=self._target_lang,
                    translated_text=translated,
                )
                session.add(cache)
                await session.commit()
        except Exception as e:
            logger.debug(f"缓存保存失败: {e}")

    async def translate(
        self,
        text: str | None,
        target_lang: str | None = None,
    ) -> str | None:
        """翻译文本

        Args:
            text: 要翻译的文本
            target_lang: 目标语言（None使用配置默认值）

        Returns:
            翻译后的文本或原文（失败/不需要时）
        """
        if not text or not text.strip():
            return text

        if self._provider is None:
            return text

        tgt_lang = target_lang or self._target_lang

        if not should_translate(text, tgt_lang, self._force_translate):
            return text

        cache_key = self._get_cache_key(text, tgt_lang)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            result = await self._provider.translate(text, tgt_lang)
            if result and result != text:
                await self._save_cache(cache_key, result)
                return result
            return text
        except Exception as e:
            logger.warning(f"翻译失败: {e}")
            return text

    async def translate_entry(
        self,
        title: str | None,
        content: str | None,
        target_lang: str | None = None,
    ) -> tuple[str | None, str | None]:
        """翻译RSS条目标题和内容

        Args:
            title: 条目标题
            content: 条目内容
            target_lang: 目标语言

        Returns:
            (翻译后标题, 翻译后内容)
        """
        tgt_lang = target_lang or self._target_lang

        translated_title = None
        translated_content = None

        if self._translate_title and title:
            translated_title = await self.translate(title, tgt_lang)

        if self._translate_content and content:
            translated_content = await self.translate(content, tgt_lang)

        return translated_title, translated_content

    def format_translated(
        self,
        original: str | None,
        translated: str | None,
        failed: bool = False,
    ) -> str | None:
        """格式化翻译结果

        Args:
            original: 原文
            translated: 译文
            failed: 是否翻译失败

        Returns:
            格式化后的文本
        """
        if failed:
            return f"{original}{self.FAILED_MARKER}" if original else None

        if not translated or translated == original:
            return original

        if self._display_original and original:
            return f"{original}{self.SEPARATOR}{translated}"

        return translated

    @property
    def is_enabled(self) -> bool:
        return self._provider is not None

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def translate_title(self) -> bool:
        return self._translate_title

    @property
    def translate_content(self) -> bool:
        return self._translate_content

    @property
    def provider_name(self) -> str:
        return self._provider.NAME if self._provider else ""
