"""Handler chain entities and normalization helpers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

HANDLER_STATUS_INHERIT = -100
HANDLER_STATUS_DISABLED = 0
HANDLER_STATUS_ENABLED = 1
SUPPORTED_HANDLER_TYPES = {"builtin", "external"}
BUILTIN_HANDLER_DEFAULT_STATUS = {
    "xml_parse": True,
    "ai_transform": True,
}


class HandlerSpec(BaseModel):
    """Declarative content handler item."""

    id: str = Field(..., min_length=1, max_length=255, description="Handler 唯一标识")
    type: str = Field(default="builtin", description="Handler 类型")
    name: str = Field(..., min_length=1, max_length=64, description="Handler 名称")
    status: int = Field(
        default=HANDLER_STATUS_INHERIT,
        description="状态: 1=启用, 0=禁用, -100=跟随默认值",
    )
    config: dict[str, Any] = Field(default_factory=dict, description="Handler 私有配置")

    def normalized(self) -> HandlerSpec:
        """Return a normalized copy."""
        handler_type = str(self.type or "").strip().lower() or "builtin"
        if handler_type not in SUPPORTED_HANDLER_TYPES:
            handler_type = "external"

        status = self.status
        if status not in {
            HANDLER_STATUS_ENABLED,
            HANDLER_STATUS_DISABLED,
            HANDLER_STATUS_INHERIT,
        }:
            status = HANDLER_STATUS_INHERIT

        return HandlerSpec(
            id=str(self.id or "").strip(),
            type=handler_type,
            name=str(self.name or "").strip(),
            status=status,
            config=_normalize_handler_config(self.config),
        )


def _normalize_handler_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, raw in value.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        normalized[normalized_key] = raw
    return normalized


def normalize_handlers(value: Any) -> list[HandlerSpec]:
    """Normalize stored handler payload to validated list."""
    if value is None or value == "":
        return []

    payload = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            payload = json.loads(stripped)
        except Exception:
            return []

    if not isinstance(payload, list):
        return []

    normalized: list[HandlerSpec] = []
    seen_ids: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            spec = HandlerSpec.model_validate(item).normalized()
        except Exception:
            continue
        if not spec.id or not spec.name or spec.id in seen_ids:
            continue
        seen_ids.add(spec.id)
        normalized.append(spec)
    return normalized


def dump_handlers(value: Any) -> list[dict[str, Any]]:
    """Dump handler payload to stable JSON-serializable list."""
    return [spec.model_dump() for spec in normalize_handlers(value)]


def handlers_json(value: Any) -> str:
    """Serialize handlers to compact stable JSON for persistence."""
    return json.dumps(dump_handlers(value), ensure_ascii=False, separators=(",", ":"))


def parse_handlers_input(value: Any) -> list[dict[str, Any]]:
    """Parse user-provided handler payload and raise on invalid non-empty input."""
    if value is None:
        return []
    if isinstance(value, list):
        return dump_handlers(value)

    normalized = str(value or "").strip()
    if not normalized:
        return []

    try:
        payload = json.loads(normalized)
    except Exception as exc:
        raise ValueError("handlers 必须是合法 JSON 数组") from exc

    if not isinstance(payload, list):
        raise ValueError("handlers 必须是 JSON 数组")
    return dump_handlers(payload)


def handler_default_enabled(name: str) -> bool:
    """Return the default enabled state for a builtin handler."""
    return BUILTIN_HANDLER_DEFAULT_STATUS.get(str(name or "").strip(), False)


def is_handler_enabled(spec: HandlerSpec | dict[str, Any]) -> bool:
    """Resolve the runtime enabled state for a handler spec."""
    normalized = (
        spec
        if isinstance(spec, HandlerSpec)
        else HandlerSpec.model_validate(spec).normalized()
    )
    if normalized.status == HANDLER_STATUS_ENABLED:
        return True
    if normalized.status == HANDLER_STATUS_DISABLED:
        return False
    return handler_default_enabled(normalized.name)


def build_ai_transform_handler(prompt: str) -> list[dict[str, Any]]:
    """Build migrated default AI transform handler from legacy ai_prompt."""
    normalized_prompt = str(prompt or "").strip()
    if not normalized_prompt:
        return []
    return [
        {
            "id": "builtin.ai_transform.default",
            "type": "builtin",
            "name": "ai_transform",
            "status": HANDLER_STATUS_ENABLED,
            "config": {"prompt": normalized_prompt},
        }
    ]
