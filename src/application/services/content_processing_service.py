"""Content processing service for RSS entries.

This service owns the optional content pipeline used by feed polling before
dispatch. It intentionally fails open: pipeline errors do not block delivery.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ...infrastructure.pipeline.filters import (
    FilterChain,
    PipelineConfig,
    build_default_chain,
)
from ...infrastructure.utils import get_logger
from ..settings import PipelineSettings

logger = get_logger()


@dataclass(slots=True)
class ContentProcessingResult:
    """Processed entry payload."""

    entry: dict[str, Any]
    filtered_out: bool = False
    engine: str = "pass-through"
    error: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


class ContentProcessingService:
    """Optional RSS entry content pipeline."""

    def __init__(
        self,
        settings: PipelineSettings | None = None,
        *,
        llm_generate_func: Callable[..., Awaitable[Any]] | None = None,
        chain: FilterChain | None = None,
    ) -> None:
        self._settings = settings or PipelineSettings()
        self._chain = chain or build_default_chain(llm_generate=llm_generate_func)

    async def process(self, entry: dict[str, Any]) -> ContentProcessingResult:
        """Run filter/enrichment pipeline for one entry.

        Errors fall back to the original entry so default push behavior is kept.
        """
        config = PipelineConfig.from_config(self._settings)
        try:
            result = await self._chain.run(dict(entry), config)
            if result.filtered_out or result.entry is None:
                return ContentProcessingResult(
                    entry=dict(entry),
                    filtered_out=True,
                    engine=result.engine,
                    error=result.error or "filtered_out",
                )
            return ContentProcessingResult(
                entry=result.entry,
                filtered_out=False,
                engine=result.engine,
                error=result.error or "",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - fail open safeguard
            logger.warning("content-processing: pipeline failed, fallback: %s", exc)
            return ContentProcessingResult(entry=dict(entry), error=str(exc))
