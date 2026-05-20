from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from astrbot_plugin_rsshub.src.application.ports.route_knowledge import (
    RouteKnowledgeDocument,
)
from astrbot_plugin_rsshub.src.application.settings import RouteKnowledgeSettings
from astrbot_plugin_rsshub.src.infrastructure.knowledge.astrbot_kb_repository import (
    AstrBotRouteKnowledgeRepository,
)


class _EmbeddingProvider:
    def meta(self):
        return SimpleNamespace(id="embedding-1")


class _RerankProvider:
    def meta(self):
        return SimpleNamespace(id="rerank-1")


def _kb_helper():
    return SimpleNamespace(
        kb=SimpleNamespace(
            kb_id="kb-1",
            kb_name="RSSHub Routes",
            description="desc",
            emoji="📡",
            embedding_provider_id="embedding-1",
            rerank_provider_id=None,
            chunk_size=256,
            chunk_overlap=32,
            top_k_dense=50,
            top_k_sparse=50,
            top_m_final=8,
        ),
        init_error=None,
        list_documents=AsyncMock(
            return_value=[
                SimpleNamespace(doc_id="doc-1", doc_name="rsshub-routes/index/a.md"),
                SimpleNamespace(doc_id="doc-2", doc_name="manual.md"),
            ]
        ),
        delete_document=AsyncMock(),
        upload_document=AsyncMock(return_value=SimpleNamespace(doc_id="doc-new")),
    )


@pytest.mark.asyncio
async def test_astrbot_route_repository_lists_only_managed_documents():
    helper = _kb_helper()
    manager = SimpleNamespace(get_kb_by_name=AsyncMock(return_value=helper))
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(kb_name="RSSHub Routes"),
    )

    docs = await repo.list_documents()

    assert [(doc.doc_id, doc.doc_name) for doc in docs] == [
        ("doc-1", "rsshub-routes/index/a.md")
    ]
    manager.get_kb_by_name.assert_awaited_once_with("RSSHub Routes")


@pytest.mark.asyncio
async def test_astrbot_route_repository_uploads_with_stable_doc_name():
    helper = _kb_helper()
    manager = SimpleNamespace(get_kb_by_name=AsyncMock(return_value=helper))
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(batch_size=8, tasks_limit=2, max_retries=1),
    )

    doc_id = await repo.upload_document(
        RouteKnowledgeDocument(
            path="docs/routes/bilibili/user.md",
            content="# Route",
            sha256="unused",
        )
    )

    assert doc_id == "doc-new"
    helper.upload_document.assert_awaited_once_with(
        file_name="rsshub-routes/docs/routes/bilibili/user.md",
        file_content=b"# Route",
        file_type="md",
        chunk_size=256,
        chunk_overlap=32,
        batch_size=8,
        tasks_limit=2,
        max_retries=1,
    )


@pytest.mark.asyncio
async def test_astrbot_route_repository_escapes_raw_tags_before_upload():
    helper = _kb_helper()
    manager = SimpleNamespace(get_kb_by_name=AsyncMock(return_value=helper))
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(batch_size=8, tasks_limit=2, max_retries=1),
    )

    await repo.upload_document(
        RouteKnowledgeDocument(
            path="docs/routes/demo.md",
            content="# Demo\n\n<input>\n</input>\n<div>text</div>",
            sha256="unused",
        )
    )

    payload = helper.upload_document.await_args.kwargs["file_content"].decode("utf-8")
    assert "&lt;input&gt;" in payload
    assert "&lt;/input&gt;" in payload
    assert "&lt;div&gt;text&lt;/div&gt;" in payload


@pytest.mark.asyncio
async def test_astrbot_route_repository_creates_kb_when_single_embedding_provider():
    created = _kb_helper()
    manager = SimpleNamespace(
        provider_manager=SimpleNamespace(
            embedding_provider_insts=[_EmbeddingProvider()],
            rerank_provider_insts=[],
        ),
        get_kb_by_name=AsyncMock(return_value=None),
        create_kb=AsyncMock(return_value=created),
    )
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(kb_name="RSSHub Routes"),
    )

    kb_id = await repo.ensure_kb()

    assert kb_id == "kb-1"
    manager.create_kb.assert_awaited_once_with(
        kb_name="RSSHub Routes",
        description="RSSHub Routes 文档，用于查找 RSSHub 路由和参数。",
        emoji="📡",
        embedding_provider_id="embedding-1",
        rerank_provider_id=None,
        chunk_size=512,
        chunk_overlap=50,
        top_k_dense=50,
        top_k_sparse=50,
        top_m_final=8,
    )


@pytest.mark.asyncio
async def test_astrbot_route_repository_uses_configured_provider_ids():
    created = _kb_helper()
    manager = SimpleNamespace(
        provider_manager=SimpleNamespace(
            embedding_provider_insts=[_EmbeddingProvider()],
            rerank_provider_insts=[_RerankProvider()],
        ),
        get_kb_by_name=AsyncMock(return_value=None),
        create_kb=AsyncMock(return_value=created),
    )
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(
            kb_name="RSSHub Routes",
            embedding_provider_id="embedding-1",
            rerank_provider_id="rerank-1",
        ),
    )

    kb_id = await repo.ensure_kb()

    assert kb_id == "kb-1"
    assert manager.create_kb.await_args.kwargs["embedding_provider_id"] == "embedding-1"
    assert manager.create_kb.await_args.kwargs["rerank_provider_id"] == "rerank-1"


@pytest.mark.asyncio
async def test_astrbot_route_repository_selects_first_embedding_provider_by_default():
    first = SimpleNamespace(meta=lambda: SimpleNamespace(id="embedding-1"))
    second = SimpleNamespace(meta=lambda: SimpleNamespace(id="embedding-2"))
    created = _kb_helper()
    manager = SimpleNamespace(
        provider_manager=SimpleNamespace(
            embedding_provider_insts=[first, second],
            rerank_provider_insts=[_RerankProvider()],
        ),
        get_kb_by_name=AsyncMock(return_value=None),
        create_kb=AsyncMock(return_value=created),
    )
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(kb_name="RSSHub Routes"),
    )

    await repo.ensure_kb()

    assert manager.create_kb.await_args.kwargs["embedding_provider_id"] == "embedding-1"
    assert manager.create_kb.await_args.kwargs["rerank_provider_id"] == "rerank-1"


@pytest.mark.asyncio
async def test_astrbot_route_repository_updates_existing_kb_with_default_rerank():
    helper = _kb_helper()
    updated = _kb_helper()
    updated.kb.rerank_provider_id = "rerank-1"
    manager = SimpleNamespace(
        provider_manager=SimpleNamespace(rerank_provider_insts=[_RerankProvider()]),
        get_kb_by_name=AsyncMock(return_value=helper),
        update_kb=AsyncMock(return_value=updated),
    )
    context = SimpleNamespace(kb_manager=manager)
    repo = AstrBotRouteKnowledgeRepository(
        context=context,
        settings=RouteKnowledgeSettings(kb_name="RSSHub Routes"),
    )

    kb_id = await repo.ensure_kb()

    assert kb_id == "kb-1"
    manager.update_kb.assert_awaited_once()
    assert manager.update_kb.await_args.kwargs["rerank_provider_id"] == "rerank-1"
