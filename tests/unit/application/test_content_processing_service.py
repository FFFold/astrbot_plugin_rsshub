from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub.src.application.services.content_processing_service import (
    ContentProcessingService,
)
from astrbot_plugin_rsshub.src.application.settings import PipelineSettings


@pytest.mark.asyncio
async def test_content_processing_filters_blacklisted_keyword():
    service = ContentProcessingService(
        PipelineSettings(keyword_blacklist=("spam",)),
    )

    result = await service.process({"title": "spam title", "summary": "body"})

    assert result.filtered_out is True
    assert result.entry["title"] == "spam title"


@pytest.mark.asyncio
async def test_content_processing_enriches_title_and_summary_with_llm_json():
    llm = AsyncMock(return_value='{"title":"标题","summary":"摘要"}')
    service = ContentProcessingService(
        PipelineSettings(ai_enrich_enabled=True),
        llm_generate_func=llm,
    )

    result = await service.process(
        {"title": "Title", "summary": "Summary", "media_urls": []}
    )

    assert result.filtered_out is False
    assert result.entry["title"] == "标题"
    assert result.entry["summary"] == "摘要"
    llm.assert_awaited_once()


@pytest.mark.asyncio
async def test_content_processing_filters_with_llm_rejection():
    llm = AsyncMock(return_value="no")
    service = ContentProcessingService(
        PipelineSettings(ai_filter_enabled=True),
        llm_generate_func=llm,
    )

    result = await service.process({"title": "Title", "summary": "Summary"})

    assert result.filtered_out is True
    assert result.entry["title"] == "Title"
    assert result.engine == "llm-filter"
    assert result.error == "llm_rejected"


@pytest.mark.asyncio
async def test_content_processing_falls_back_on_pipeline_error():
    class ExplodingChain:
        async def run(self, entry: dict[str, Any], config: Any):
            raise RuntimeError("boom")

    service = ContentProcessingService(
        PipelineSettings(ai_filter_enabled=True),
        chain=ExplodingChain(),
    )

    result = await service.process({"title": "Title", "summary": "Summary"})

    assert result.filtered_out is False
    assert result.entry["title"] == "Title"
    assert result.error == "boom"
