"""AstrBot knowledge-base adapter for RSSHub Routes documents."""

from __future__ import annotations

import html
import re
from typing import Any

from ...application.ports.route_knowledge import (
    RouteKnowledgeDocument,
    RouteKnowledgeDocumentRecord,
)
from ...application.services.route_knowledge_service import managed_doc_name
from ...application.settings import RouteKnowledgeSettings

DEFAULT_KB_EMOJI = "📡"
_RAW_TAG_PATTERN = re.compile(r"</?[A-Za-z][^>\n]*>")


class AstrBotRouteKnowledgeRepository:
    """Upload/delete RSSHub route docs through AstrBot's KB runtime API."""

    def __init__(self, *, context: Any, settings: RouteKnowledgeSettings) -> None:
        self._context = context
        self._settings = settings

    async def ensure_kb(self) -> str:
        kb_helper = await self._get_or_create_kb()
        return str(kb_helper.kb.kb_id)

    async def list_documents(self) -> list[RouteKnowledgeDocumentRecord]:
        kb_helper = await self._require_kb()
        docs = await kb_helper.list_documents(offset=0, limit=100000)
        return [
            RouteKnowledgeDocumentRecord(
                doc_id=str(doc.doc_id),
                doc_name=str(doc.doc_name),
            )
            for doc in docs
            if str(doc.doc_name).startswith("rsshub-routes/")
        ]

    async def delete_document(self, doc_id: str) -> None:
        kb_helper = await self._require_kb()
        await kb_helper.delete_document(doc_id)

    async def upload_document(self, document: RouteKnowledgeDocument) -> str:
        kb_helper = await self._require_kb()
        sanitized_content = _sanitize_document_content_for_embedding(document.content)
        file_name = managed_doc_name(document.path)
        try:
            doc = await kb_helper.upload_document(
                file_name=file_name,
                file_content=sanitized_content.encode("utf-8"),
                file_type="md",
                chunk_size=int(kb_helper.kb.chunk_size or 512),
                chunk_overlap=int(kb_helper.kb.chunk_overlap or 50),
                batch_size=self._settings.batch_size,
                tasks_limit=self._settings.tasks_limit,
                max_retries=self._settings.max_retries,
            )
        except Exception as exc:
            raise RuntimeError(f"上传知识库文档失败: {document.path}: {exc}") from exc
        return str(doc.doc_id)

    async def _require_kb(self):
        kb_manager = self._get_kb_manager()
        kb_helper = await kb_manager.get_kb_by_name(self._settings.kb_name)
        if not kb_helper:
            raise ValueError(
                f"知识库 `{self._settings.kb_name}` 不存在。"
                "请先在 AstrBot 知识库管理中创建并配置 embedding，"
                "或使用 /rsshub_kb_init 自动创建。"
            )
        if getattr(kb_helper, "init_error", None):
            raise ValueError(
                f"知识库 `{self._settings.kb_name}` 不可用: {kb_helper.init_error}"
            )
        return kb_helper

    async def _get_or_create_kb(self):
        kb_manager = self._get_kb_manager()
        kb_helper = await kb_manager.get_kb_by_name(self._settings.kb_name)
        if kb_helper:
            if getattr(kb_helper, "init_error", None):
                raise ValueError(
                    f"知识库 `{self._settings.kb_name}` 不可用: {kb_helper.init_error}"
                )
            rerank_provider_id = self._resolve_rerank_provider_id()
            if (
                rerank_provider_id
                and not getattr(kb_helper.kb, "rerank_provider_id", None)
                and hasattr(kb_manager, "update_kb")
            ):
                updated = await kb_manager.update_kb(
                    kb_id=kb_helper.kb.kb_id,
                    kb_name=kb_helper.kb.kb_name,
                    description=getattr(kb_helper.kb, "description", None),
                    emoji=getattr(kb_helper.kb, "emoji", None),
                    embedding_provider_id=getattr(
                        kb_helper.kb, "embedding_provider_id", None
                    ),
                    rerank_provider_id=rerank_provider_id,
                    chunk_size=getattr(kb_helper.kb, "chunk_size", None),
                    chunk_overlap=getattr(kb_helper.kb, "chunk_overlap", None),
                    top_k_dense=getattr(kb_helper.kb, "top_k_dense", None),
                    top_k_sparse=getattr(kb_helper.kb, "top_k_sparse", None),
                    top_m_final=getattr(kb_helper.kb, "top_m_final", None),
                )
                if updated:
                    kb_helper = updated
            return kb_helper

        embedding_provider_id = self._resolve_embedding_provider_id()
        if not embedding_provider_id:
            raise ValueError(
                f"知识库 `{self._settings.kb_name}` 不存在，且无法自动选择 "
                "Embedding Provider。请先在插件配置中选择向量模型，"
                "或在 AstrBot 中配置可用的 embedding 模型。"
            )
        rerank_provider_id = self._resolve_rerank_provider_id()
        return await kb_manager.create_kb(
            kb_name=self._settings.kb_name,
            description="RSSHub Routes 文档，用于查找 RSSHub 路由和参数。",
            emoji=DEFAULT_KB_EMOJI,
            embedding_provider_id=embedding_provider_id,
            rerank_provider_id=rerank_provider_id,
            chunk_size=512,
            chunk_overlap=50,
            top_k_dense=50,
            top_k_sparse=50,
            top_m_final=8,
        )

    def _get_kb_manager(self):
        kb_manager = getattr(self._context, "kb_manager", None)
        if kb_manager is None:
            raise RuntimeError("当前 AstrBot 运行环境未提供知识库管理器")
        return kb_manager

    def _resolve_embedding_provider_id(self) -> str:
        preferred_id = (self._settings.embedding_provider_id or "").strip()
        if preferred_id:
            if self._find_provider_by_id(preferred_id, provider_kind="embedding"):
                return preferred_id
            raise ValueError(
                f"未找到可用的 Embedding Provider: {preferred_id}。"
                "请检查 RSSHub Routes 知识库配置中的向量模型。"
            )
        provider = self._first_provider("embedding")
        return self._provider_id(provider) if provider else ""

    def _resolve_rerank_provider_id(self) -> str | None:
        preferred_id = (self._settings.rerank_provider_id or "").strip()
        if preferred_id:
            if self._find_provider_by_id(preferred_id, provider_kind="rerank"):
                return preferred_id
            raise ValueError(
                f"未找到可用的 Rerank Provider: {preferred_id}。"
                "请检查 RSSHub Routes 知识库配置中的重排序模型，或留空使用默认值。"
            )
        provider = self._first_provider("rerank")
        return self._provider_id(provider) if provider else None

    def _find_provider_by_id(
        self, provider_id: str, *, provider_kind: str
    ) -> Any | None:
        getter = getattr(self._context, "get_provider_by_id", None)
        if callable(getter):
            provider = getter(provider_id)
            if provider and self._provider_matches_kind(provider, provider_kind):
                return provider
        for provider in self._provider_list(provider_kind):
            if self._provider_id(provider) == provider_id:
                return provider
        return None

    def _first_provider(self, provider_kind: str) -> Any | None:
        providers = self._provider_list(provider_kind)
        return providers[0] if providers else None

    def _provider_list(self, provider_kind: str) -> list[Any]:
        if provider_kind == "embedding":
            getter = getattr(self._context, "get_all_embedding_providers", None)
            if callable(getter):
                providers = getter()
                if isinstance(providers, list):
                    return providers
            attr_name = "embedding_provider_insts"
        else:
            attr_name = "rerank_provider_insts"
        kb_manager = self._get_kb_manager()
        provider_manager = getattr(kb_manager, "provider_manager", None) or getattr(
            self._context, "provider_manager", None
        )
        providers = getattr(provider_manager, attr_name, []) if provider_manager else []
        return providers if isinstance(providers, list) else []

    @staticmethod
    def _provider_id(provider: Any) -> str:
        if provider is None:
            return ""
        try:
            meta = provider.meta()
            return str(meta.id or "")
        except Exception:
            config = getattr(provider, "provider_config", {}) or {}
            if isinstance(config, dict):
                return str(config.get("id") or "")
        return ""

    def _provider_matches_kind(self, provider: Any, provider_kind: str) -> bool:
        if provider in self._provider_list(provider_kind):
            return True
        class_name = provider.__class__.__name__.lower()
        return provider_kind in class_name


def _sanitize_document_content_for_embedding(content: str) -> str:
    """Escape raw HTML/XML-like tags that can break embedding provider validation."""
    text = str(content or "")
    if not text:
        return text
    return _RAW_TAG_PATTERN.sub(lambda match: html.escape(match.group(0)), text)
