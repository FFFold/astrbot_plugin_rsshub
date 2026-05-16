"""过滤器链 - 基础过滤器集合

提供开箱即用的过滤器实现：关键词过滤、AI 筛选、翻译、透传。
"""

from __future__ import annotations

import json
import re
from typing import Any

from ...utils import get_logger
from . import BaseFilter, FilterContext, FilterResult

logger = get_logger()


class PassThroughFilter(BaseFilter):
    """透传过滤器（终保底）

    始终返回原文，确保过滤链必有输出。
    """

    name: str = "pass-through"

    async def process(self, entry: dict[str, Any], context: FilterContext) -> FilterResult:
        return FilterResult(entry=entry, engine="pass-through")


class KeywordFilter(BaseFilter):
    """关键词过滤器

    基于本地规则过滤：
    - 标题/摘要关键词黑白名单
    - 最小内容长度
    - 最小媒体数量
    """

    name: str = "keyword"

    async def process(self, entry: dict[str, Any], context: FilterContext) -> FilterResult:
        config = context.config

        title = str(entry.get("title", "") or "").strip()
        summary = str(entry.get("summary", "") or entry.get("content", "") or "").strip()
        full_text = f"{title}\n{summary}".lower()

        if config.keyword_blacklist:
            for kw in config.keyword_blacklist:
                if kw.lower() in full_text:
                    logger.debug("keyword-filter: blacklisted '%s' matched, discarding", kw)
                    return FilterResult(
                        entry=None,
                        engine="keyword",
                        filtered_out=True,
                        error=f"blacklisted:{kw}",
                    )

        if config.keyword_whitelist:
            matched = any(kw.lower() in full_text for kw in config.keyword_whitelist)
            if not matched and full_text:
                logger.debug("keyword-filter: no whitelist keyword matched, discarding")
                return FilterResult(
                    entry=None,
                    engine="keyword",
                    filtered_out=True,
                    error="whitelist:no_match",
                )

        if config.min_content_length > 0 and len(full_text) < config.min_content_length:
            logger.debug("keyword-filter: content too short (%d < %d)", len(full_text), config.min_content_length)
            return FilterResult(
                entry=None,
                engine="keyword",
                filtered_out=True,
                error="too_short",
            )

        if config.min_media_count > 0:
            media_count = len(entry.get("media_urls", []) or [])
            if media_count < config.min_media_count:
                logger.debug("keyword-filter: media too few (%d < %d)", media_count, config.min_media_count)
                return FilterResult(
                    entry=None,
                    engine="keyword",
                    filtered_out=True,
                    error="too_few_media",
                )

        return FilterResult(entry=entry, engine="keyword")


class LLMFilter(BaseFilter):
    """AI 过滤器

    使用 LLM 判断条目是否应该保留。
    默认关闭，需显式启用并配置 prompt。
    """

    name: str = "llm-filter"

    def __init__(self, llm_generate_func=None):
        self._llm_generate = llm_generate_func

    async def process(self, entry: dict[str, Any], context: FilterContext) -> FilterResult:
        if not context.config.ai_filter_enabled:
            return FilterResult(entry=entry, engine="llm-filter:disabled")

        if self._llm_generate is None:
            logger.warning("llm-filter: llm_generate not available, passing through")
            return FilterResult(entry=entry, engine="llm-filter:no-llm")

        prompt = context.config.ai_filter_prompt or (
            "根据以下 RSS 条目判断是否应推送给用户。"
            "如果内容有价值则回复 yes，否则回复 no。"
            "只回复 yes 或 no。\n\n"
            f"标题：{entry.get('title', '')}\n"
            f"摘要：{entry.get('summary', '') or entry.get('content', '')}"
        )

        try:
            result = await self._llm_generate(prompt=prompt)
            answer = str(result).strip().lower() if result else ""
            if answer == "no":
                logger.debug("llm-filter: LLM rejected entry: %s", entry.get("title", ""))
                return FilterResult(
                    entry=None,
                    engine="llm-filter",
                    filtered_out=True,
                    error="llm_rejected",
                )
            return FilterResult(entry=entry, engine="llm-filter")
        except Exception as e:
            logger.warning("llm-filter: LLM call failed, passing through: %s", e)
            return FilterResult(entry=entry, engine="llm-filter:fallback")


class LLMEnrichFilter(BaseFilter):
    """AI 增强过滤器

    使用 LLM 一次性完成总结 + 翻译 + 改写。
    默认关闭，需显式启用。
    """

    name: str = "llm-enrich"

    def __init__(self, llm_generate_func=None):
        self._llm_generate = llm_generate_func

    async def process(self, entry: dict[str, Any], context: FilterContext) -> FilterResult:
        if not context.config.ai_enrich_enabled:
            return FilterResult(entry=entry, engine="llm-enrich:disabled")

        if self._llm_generate is None:
            logger.warning("llm-enrich: llm_generate not available, passing through")
            return FilterResult(entry=entry, engine="llm-enrich:no-llm")

        title = str(entry.get("title", "") or "")
        summary = str(entry.get("summary", "") or entry.get("content", "") or "")

        prompt_template = context.config.ai_enrich_prompt or (
            "请处理以下 RSS 条目，返回 JSON：\n"
            "{\"title\": \"中文标题\", \"summary\": \"中文摘要（150字内）\"}\n\n"
            f"标题：{title}\n摘要：{summary}"
        )

        import json

        try:
            result = await self._llm_generate(prompt=prompt_template)
            raw = str(result).strip() if result else ""
            parsed = self._parse_json_response(raw)
            if parsed and parsed.get("title"):
                enriched = dict(entry)
                enriched["title"] = parsed["title"]
                enriched["summary"] = parsed.get("summary", "") or enriched.get("summary", "")
                return FilterResult(entry=enriched, engine="llm-enrich")
            return FilterResult(entry=entry, engine="llm-enrich:parse-failed")
        except Exception as e:
            logger.warning("llm-enrich: LLM call failed, passing through: %s", e)
            return FilterResult(entry=entry, engine="llm-enrich:fallback")

    @staticmethod
    def _parse_json_response(raw: str) -> dict | None:
        if not raw:
            return None
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", raw)
            if raw.endswith("```"):
                raw = raw[:-3]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and first < last:
            try:
                return json.loads(raw[first : last + 1])
            except json.JSONDecodeError:
                pass
        return None


class TranslationFilter(BaseFilter):
    """翻译过滤器

    使用传统翻译引擎（Google / Baidu）。
    """

    name: str = "translation"

    def __init__(self, translate_func=None):
        self._translate = translate_func

    async def process(self, entry: dict[str, Any], context: FilterContext) -> FilterResult:
        if not context.config.translate_enabled:
            return FilterResult(entry=entry, engine="translation:disabled")

        if self._translate is None:
            return FilterResult(entry=entry, engine="translation:no-engine")

        try:
            title = str(entry.get("title", "") or "")
            summary = str(entry.get("summary", "") or "")

            translated = await self._translate(
                texts=[title, summary] if summary else [title],
                target_lang=context.config.translate_target_lang,
            )

            if not translated:
                return FilterResult(entry=entry, engine="translation:empty-result")

            enriched = dict(entry)
            # 保留原文供 LLM 使用
            enriched.setdefault("_source_title", title)
            enriched.setdefault("_source_summary", summary)

            if len(translated) >= 1:
                enriched["title"] = translated[0]
            if len(translated) >= 2:
                enriched["summary"] = translated[1]

            return FilterResult(entry=enriched, engine=f"translation:{context.config.translate_engine}")
        except Exception as e:
            logger.warning("translation-filter: failed, passing through: %s", e)
            return FilterResult(entry=entry, engine="translation:fallback")


def build_default_chain(
    llm_generate=None,
    translate_func=None,
) -> FilterChain:
    """构建默认过滤器链。"""
    from . import FilterChain

    filters: list[BaseFilter] = [
        KeywordFilter(),
        LLMFilter(llm_generate_func=llm_generate),
        LLMEnrichFilter(llm_generate_func=llm_generate),
        TranslationFilter(translate_func=translate_func),
        PassThroughFilter(),
    ]
    return FilterChain(filters)
