"""Entry content handler runtime for RSS push pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

try:
    from astrbot.core.provider.provider import Provider
except Exception:  # pragma: no cover - lightweight test fallback
    class Provider:  # type: ignore[no-redef]
        pass

from ...domain.entities.handlers import (
    HandlerSpec,
    is_handler_enabled,
    normalize_handlers,
)
from ...domain.entities.subscription import (
    HANDLERS_MODE_DISABLED,
    HANDLERS_MODE_INHERIT,
    HANDLERS_MODE_OVERRIDE,
    Subscription,
)
from ...domain.entities.user import User
from ...infrastructure.utils import get_logger
from .html_parser import HTMLParser

logger = get_logger()


@dataclass(frozen=True, slots=True)
class EntryContentContext:
    """Raw entry payload before formatting for one subscription."""

    title: str
    summary: str
    content: str
    link: str
    author: str
    feed_title: str
    feed_link: str
    raw_xml: str = ""
    media_urls: tuple[str, ...] = ()
    media_items: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class HandlerProcessResult:
    """Content handler result plus runtime trace."""

    entry: EntryContentContext
    allow: bool = True
    reason: str = ""
    trace: tuple[dict[str, Any], ...] = ()


class ContentHandlerRuntime:
    """Resolve and execute builtin entry handlers."""

    def __init__(self, context: Any | None = None):
        self._context = context

    def resolve_handlers(
        self,
        *,
        subscription: Subscription,
        user: User | None,
    ) -> list[HandlerSpec]:
        mode = str(getattr(subscription, "handlers_mode", "") or "").strip().lower()
        if mode == HANDLERS_MODE_DISABLED:
            active = []
        elif mode == HANDLERS_MODE_OVERRIDE:
            active = subscription.handlers
        else:
            active = user.handlers if user else []
            if mode not in {
                HANDLERS_MODE_INHERIT,
                HANDLERS_MODE_OVERRIDE,
                HANDLERS_MODE_DISABLED,
            } and subscription.handlers:
                active = subscription.handlers
        return normalize_handlers(active)

    async def process_entry(
        self,
        *,
        subscription: Subscription,
        user: User | None,
        entry: EntryContentContext,
        session_id: str | None = None,
    ) -> EntryContentContext:
        result = await self.process_entry_with_trace(
            subscription=subscription,
            user=user,
            entry=entry,
            session_id=session_id,
        )
        return result.entry

    async def process_entry_with_trace(
        self,
        *,
        subscription: Subscription,
        user: User | None,
        entry: EntryContentContext,
        session_id: str | None = None,
    ) -> HandlerProcessResult:
        result = entry
        trace: list[dict[str, Any]] = []
        for spec in self.resolve_handlers(subscription=subscription, user=user):
            if not is_handler_enabled(spec):
                trace.append(
                    {
                        "id": spec.id,
                        "name": spec.name,
                        "status": "disabled",
                    }
                )
                continue
            if spec.type != "builtin":
                logger.debug("跳过 external handler: %s", spec.id)
                trace.append(
                    {
                        "id": spec.id,
                        "name": spec.name,
                        "status": "skipped",
                        "reason": "external handler",
                    }
                )
                continue
            try:
                if spec.name == "xml_parse":
                    result = await self._run_xml_parse(result)
                    trace.append(
                        {
                            "id": spec.id,
                            "name": spec.name,
                            "status": "ok",
                        }
                    )
                elif spec.name == "ai_filter":
                    allowed, reason = await self._run_ai_filter(
                        result,
                        spec.config,
                        session_id=session_id,
                    )
                    trace.append(
                        {
                            "id": spec.id,
                            "name": spec.name,
                            "status": "ok",
                            "allow": allowed,
                            "reason": reason,
                        }
                    )
                    if not allowed:
                        return HandlerProcessResult(
                            entry=result,
                            allow=False,
                            reason=reason,
                            trace=tuple(trace),
                        )
                elif spec.name == "ai_transform":
                    result = await self._run_ai_transform(
                        result,
                        spec.config,
                        session_id=session_id,
                    )
                    trace.append(
                        {
                            "id": spec.id,
                            "name": spec.name,
                            "status": "ok",
                        }
                    )
                else:
                    logger.debug("未知内置 handler，已跳过: %s", spec.name)
                    trace.append(
                        {
                            "id": spec.id,
                            "name": spec.name,
                            "status": "skipped",
                            "reason": "unknown builtin handler",
                        }
                    )
            except Exception as exc:
                logger.warning(
                    "handler 执行失败，已回退上一步结果: %s (%s)",
                    spec.id,
                    exc,
                )
                trace.append(
                    {
                        "id": spec.id,
                        "name": spec.name,
                        "status": "error",
                        "reason": str(exc),
                    }
                )
        return HandlerProcessResult(entry=result, trace=tuple(trace))

    async def _run_xml_parse(self, entry: EntryContentContext) -> EntryContentContext:
        html_source = entry.content or entry.summary
        if not html_source:
            return entry
        parsed = await HTMLParser(
            html_source,
            feed_link=entry.link or entry.feed_link,
        ).parse()
        plain = parsed.html_tree.get_plain().strip()
        if not plain:
            return entry
        summary = (
            plain
            if not entry.summary or entry.summary == entry.content
            else entry.summary
        )
        content = plain
        return replace(entry, summary=summary, content=content)

    async def _run_ai_transform(
        self,
        entry: EntryContentContext,
        config: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> EntryContentContext:
        prompt = str((config or {}).get("prompt") or "").strip()
        if not prompt or self._context is None:
            return entry

        provider = self._resolve_provider(session_id=session_id)
        if provider is None:
            logger.warning("ai_transform 跳过：当前没有可用的对话模型 provider")
            return entry

        source_payload = {
            "title": entry.title,
            "summary": entry.summary,
            "content": entry.content,
            "link": entry.link,
            "author": entry.author,
            "feed_title": entry.feed_title,
            "feed_link": entry.feed_link,
            "media_urls": list(entry.media_urls),
        }
        request_prompt = (
            "你是 RSS 内容处理器。根据用户要求改写条目，并只返回 JSON。"
            "如果某字段不需要修改，可以原样返回。"
            '\n返回格式: {"title":"...","summary":"...","content":"..."}'
            f"\n用户要求:\n{prompt}"
            f"\n\n条目数据:\n{json.dumps(source_payload, ensure_ascii=False)}"
        )
        response = await provider.text_chat(
            prompt=request_prompt,
            session_id=session_id or "rsshub-handlers",
            contexts=[],
            persist=False,
        )
        payload = str(getattr(response, "completion_text", "") or "").strip()
        if not payload:
            return entry

        try:
            parsed = json.loads(payload)
        except Exception as exc:
            raise ValueError(f"ai_transform 输出不是合法 JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("ai_transform 输出必须是 JSON 对象")

        title = str(parsed.get("title") or entry.title).strip()
        summary = str(parsed.get("summary") or entry.summary).strip()
        content = str(parsed.get("content") or entry.content).strip()
        return replace(
            entry,
            title=title or entry.title,
            summary=summary or entry.summary,
            content=content or entry.content,
        )

    async def _run_ai_filter(
        self,
        entry: EntryContentContext,
        config: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> tuple[bool, str]:
        prompt = str((config or {}).get("prompt") or "").strip()
        if not prompt or self._context is None:
            return True, "ai_filter 未配置 prompt 或 provider 上下文"

        provider = self._resolve_provider(session_id=session_id)
        if provider is None:
            logger.warning("ai_filter 放行：当前没有可用的对话模型 provider")
            return True, "provider unavailable"

        input_scope = str((config or {}).get("input_scope") or "text").strip()
        if input_scope not in {"text", "raw_xml", "both"}:
            input_scope = "text"
        source_payload = {
            "title": entry.title,
            "summary": entry.summary,
            "content": entry.content,
            "link": entry.link,
            "author": entry.author,
            "feed_title": entry.feed_title,
            "feed_link": entry.feed_link,
        }
        if input_scope in {"raw_xml", "both"}:
            source_payload["raw_xml"] = entry.raw_xml
        if input_scope == "raw_xml":
            source_payload = {
                "title": entry.title,
                "link": entry.link,
                "feed_title": entry.feed_title,
                "raw_xml": entry.raw_xml,
            }

        request_prompt = (
            "你是 RSS 内容过滤器。根据用户要求判断条目是否允许推送，只返回 JSON。"
            '\n返回格式: {"allow":true,"reason":"..."}'
            "\nallow=false 表示跳过推送；reason 用一句话说明原因。"
            f"\n用户要求:\n{prompt}"
            f"\n\n条目数据:\n{json.dumps(source_payload, ensure_ascii=False)}"
        )
        response = await provider.text_chat(
            prompt=request_prompt,
            session_id=session_id or "rsshub-handlers",
            contexts=[],
            persist=False,
        )
        payload = str(getattr(response, "completion_text", "") or "").strip()
        if not payload:
            logger.warning("ai_filter 放行：AI 返回为空")
            return True, "empty response"
        try:
            parsed = json.loads(payload)
        except Exception as exc:
            logger.warning("ai_filter 放行：AI 返回非法 JSON: %s", exc)
            return True, "invalid json"
        if not isinstance(parsed, dict) or not isinstance(parsed.get("allow"), bool):
            logger.warning("ai_filter 放行：AI 返回结构无效")
            return True, "invalid schema"
        reason = str(parsed.get("reason") or "").strip()
        try:
            reason_max_length = int((config or {}).get("reason_max_length") or 120)
        except (TypeError, ValueError):
            reason_max_length = 120
        if reason_max_length > 0 and len(reason) > reason_max_length:
            reason = reason[:reason_max_length].rstrip()
        return bool(parsed["allow"]), reason

    def _resolve_provider(self, *, session_id: str | None = None) -> Provider | None:
        getter = getattr(self._context, "get_using_provider", None)
        if getter is None:
            return None
        provider = getter(session_id) if session_id else getter()
        return provider if callable(getattr(provider, "text_chat", None)) else None
