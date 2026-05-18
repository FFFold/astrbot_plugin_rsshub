"""过滤器链核心接口

采用 Chain of Responsibility 模式构建内容处理管线。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ...utils import get_logger

logger = get_logger()


@dataclass
class PipelineConfig:
    """管线配置"""

    keyword_blacklist: list[str] = field(default_factory=list)
    keyword_whitelist: list[str] | None = None
    min_content_length: int = 0
    min_media_count: int = 0
    ai_filter_enabled: bool = False
    ai_filter_prompt: str = ""
    ai_enrich_enabled: bool = False
    ai_enrich_prompt: str = ""
    ai_timeout_seconds: int = 15

    @classmethod
    def from_config(cls, config: Any) -> PipelineConfig:
        return cls(
            keyword_blacklist=list(getattr(config, "keyword_blacklist", []) or []),
            keyword_whitelist=list(getattr(config, "keyword_whitelist", None) or [])
            or None,
            min_content_length=int(getattr(config, "min_content_length", 0) or 0),
            min_media_count=int(getattr(config, "min_media_count", 0) or 0),
            ai_filter_enabled=bool(getattr(config, "ai_filter_enabled", False)),
            ai_filter_prompt=str(getattr(config, "ai_filter_prompt", "") or ""),
            ai_enrich_enabled=bool(getattr(config, "ai_enrich_enabled", False)),
            ai_enrich_prompt=str(getattr(config, "ai_enrich_prompt", "") or ""),
            ai_timeout_seconds=int(getattr(config, "ai_timeout_seconds", 15) or 15),
        )


class FilterContext:
    """过滤器上下文，贯穿整个链路的共享状态。"""

    def __init__(self, entry: dict[str, Any], config: PipelineConfig):
        self.entry: dict[str, Any] = entry
        self.config: PipelineConfig = config
        self.stats: dict[str, dict] = {}
        self.abort: bool = False


@dataclass
class FilterResult:
    """过滤器处理结果。"""

    entry: dict[str, Any] | None = None
    error: str | None = None
    engine: str = "unknown"
    filtered_out: bool = False


class BaseFilter(ABC):
    """过滤器基类。所有过滤器继承此类。"""

    name: str = "base"

    @abstractmethod
    async def process(
        self, entry: dict[str, Any], context: FilterContext
    ) -> FilterResult: ...


class FilterChain:
    """过滤器链，按顺序执行多个过滤器。"""

    def __init__(self, filters: list[BaseFilter]):
        self._filters = filters

    async def run(self, entry: dict[str, Any], config: PipelineConfig) -> FilterResult:
        """执行过滤器链。

        Args:
            entry: 待处理的条目
            config: 管线配置

        Returns:
            过滤器链最终输出
        """
        context = FilterContext(entry=entry, config=config)
        current = FilterResult(entry=entry)

        for filter_ in self._filters:
            if context.abort:
                logger.debug("filter-chain: abort=True, stopping at %s", filter_.name)
                break
            if current.entry is None:
                logger.debug(
                    "filter-chain: entry discarded at %s, stopping", filter_.name
                )
                break

            try:
                current = await filter_.process(current.entry, context)
                context.stats[filter_.name] = {
                    "ok": current.error is None,
                    "engine": current.engine,
                    "filtered_out": current.filtered_out,
                }
            except Exception as e:
                logger.warning("filter-chain: %s raised %s, skipping", filter_.name, e)
                context.stats[filter_.name] = {
                    "ok": False,
                    "error": str(e),
                }
                continue

        return current

    @property
    def filters(self) -> list[BaseFilter]:
        return list(self._filters)


# 延迟导入避免循环依赖；具体过滤器实现在 base.py 中。
from .base import (  # noqa: E402,I001
    KeywordFilter as KeywordFilter,
    LLMEnrichFilter as LLMEnrichFilter,
    LLMFilter as LLMFilter,
    PassThroughFilter as PassThroughFilter,
    build_default_chain as build_default_chain,
)
