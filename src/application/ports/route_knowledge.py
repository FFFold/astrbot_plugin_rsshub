"""Ports for RSSHub Routes knowledge-base synchronization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RouteKnowledgeFile:
    """A single source document listed in the routes knowledge manifest."""

    path: str
    sha256: str
    size: int | None = None
    title: str = ""
    kind: str = ""


@dataclass(frozen=True)
class RouteKnowledgeManifest:
    """Normalized routes knowledge manifest."""

    files: tuple[RouteKnowledgeFile, ...]
    version: str = ""
    generated_at: str = ""
    source: str = ""
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RouteKnowledgeDocument:
    """Downloaded document content ready for KB upload."""

    path: str
    content: str
    sha256: str


@dataclass(frozen=True)
class RouteKnowledgeDocumentRecord:
    """Document record currently stored in the target KB."""

    doc_id: str
    doc_name: str


class RouteKnowledgeSource(Protocol):
    """Source adapter for metadata and markdown document content."""

    async def fetch_manifest(self) -> RouteKnowledgeManifest:
        """Fetch and normalize source metadata."""

    async def fetch_document(self, file: RouteKnowledgeFile) -> RouteKnowledgeDocument:
        """Fetch one document listed in the manifest."""

    async def close(self) -> None:
        """Release adapter resources."""


class RouteKnowledgeRepository(Protocol):
    """Target knowledge-base adapter."""

    async def ensure_kb(self) -> str:
        """Ensure the configured KB exists and return its ID."""

    async def list_documents(self) -> list[RouteKnowledgeDocumentRecord]:
        """List documents currently stored in the target KB."""

    async def delete_document(self, doc_id: str) -> None:
        """Delete one stored KB document."""

    async def upload_document(self, document: RouteKnowledgeDocument) -> str:
        """Upload one document and return the created doc ID."""
