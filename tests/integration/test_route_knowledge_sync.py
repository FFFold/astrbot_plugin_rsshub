from __future__ import annotations

import hashlib
import json

import pytest
from astrbot_plugin_rsshub.src.application.ports.route_knowledge import (
    RouteKnowledgeDocument,
    RouteKnowledgeDocumentRecord,
)
from astrbot_plugin_rsshub.src.application.services.route_knowledge_service import (
    RouteKnowledgeSyncService,
    managed_doc_name,
)
from astrbot_plugin_rsshub.src.infrastructure.config import RouteKnowledgeSettings
from astrbot_plugin_rsshub.src.infrastructure.knowledge.route_source import (
    FallbackRouteKnowledgeSource,
    LocalRouteKnowledgeSource,
    _join_raw_url,
    normalize_route_manifest,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _FakeRepository:
    def __init__(self):
        self.docs: dict[str, str] = {}
        self.uploaded: list[str] = []

    async def ensure_kb(self):
        return "kb-1"

    async def list_documents(self):
        return [
            RouteKnowledgeDocumentRecord(doc_id=doc_id, doc_name=doc_name)
            for doc_id, doc_name in self.docs.items()
        ]

    async def delete_document(self, doc_id: str):
        self.docs.pop(doc_id, None)

    async def upload_document(self, document):
        doc_id = f"doc-{len(self.docs) + 1}"
        doc_name = managed_doc_name(document.path)
        self.docs[doc_id] = doc_name
        self.uploaded.append(doc_name)
        return doc_id


class _PrimaryDocumentSource:
    def __init__(self):
        self.closed = False

    async def fetch_manifest(self):
        return normalize_route_manifest(
            {
                "files": [
                    {"path": "docs/routes/fallback.md", "sha256": _sha("# Fallback")}
                ]
            },
            source="primary",
        )

    async def fetch_document(self, file):
        raise OSError(f"primary missing {file.path}")

    async def close(self):
        self.closed = True


class _FallbackDocumentSource:
    def __init__(self):
        self.closed = False
        self.document_fetches: list[str] = []

    async def fetch_manifest(self):
        return normalize_route_manifest(
            {
                "files": [
                    {"path": "docs/routes/fallback.md", "sha256": _sha("# Fallback")}
                ]
            },
            source="fallback",
        )

    async def fetch_document(self, file):
        self.document_fetches.append(file.path)
        return RouteKnowledgeDocument(
            path=file.path,
            content="# Fallback",
            sha256=file.sha256,
        )

    async def close(self):
        self.closed = True


def test_normalize_route_manifest_accepts_mapping_shape():
    raw = {
        "version": "abc",
        "files": {
            "index/namespaces.md": {"sha256": "1"},
            "index/bilibili.md": {"sha": "sha256:2"},
            "docs/routes/bilibili/user.md": {"sha256": "3"},
            "README.md": {"sha256": "ignored"},
        },
    }

    manifest = normalize_route_manifest(raw)

    assert [item.path for item in manifest.files] == [
        "docs/routes/bilibili/user.md",
        "index/bilibili.md",
        "index/namespaces.md",
    ]
    assert manifest.files[1].sha256 == "2"


def test_join_raw_url_preserves_raw_proxy_prefix():
    url = _join_raw_url(
        "https://ghfast.top/https://raw.githubusercontent.com/FlanChanXwO/astrbot_plugin_rsshub/rsshub-routes-knowledgebase",
        "docs/routes/bilibili/user timeline.md",
    )

    assert url == (
        "https://ghfast.top/https://raw.githubusercontent.com/"
        "FlanChanXwO/astrbot_plugin_rsshub/rsshub-routes-knowledgebase/"
        "docs/routes/bilibili/user%20timeline.md"
    )


@pytest.mark.asyncio
async def test_auto_source_falls_back_for_manifest_and_documents():
    primary = _PrimaryDocumentSource()
    fallback = _FallbackDocumentSource()
    source = FallbackRouteKnowledgeSource(primary, fallback)

    manifest = await source.fetch_manifest()
    document = await source.fetch_document(manifest.files[0])

    assert manifest.source == "primary"
    assert document.content == "# Fallback"
    assert fallback.document_fetches == ["docs/routes/fallback.md"]

    await source.close()
    assert primary.closed is True
    assert fallback.closed is True


@pytest.mark.asyncio
async def test_local_route_knowledge_sync_imports_manifest_docs(tmp_path):
    docs_dir = tmp_path / "docs" / "routes" / "bilibili"
    index_dir = tmp_path / "index"
    docs_dir.mkdir(parents=True)
    index_dir.mkdir(parents=True)
    files = {
        "index/namespaces.md": "# Namespaces",
        "index/bilibili.md": "# Bilibili",
        "docs/routes/bilibili/user.md": "# User route",
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    metadata = {
        "version": "v1",
        "files": [
            {"path": path, "sha256": _sha(content)} for path, content in files.items()
        ],
    }
    (tmp_path / "metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    repo = _FakeRepository()
    service = RouteKnowledgeSyncService(
        settings=RouteKnowledgeSettings(local_source_dir=str(tmp_path)),
        source=LocalRouteKnowledgeSource(str(tmp_path)),
        repository=repo,
        state_dir=tmp_path / ".state",
    )

    result = await service.sync(task_id="local-sync")

    assert result.success is True
    assert set(repo.uploaded) == {
        managed_doc_name("index/namespaces.md"),
        managed_doc_name("index/bilibili.md"),
        managed_doc_name("docs/routes/bilibili/user.md"),
    }
    status = await service.get_status()
    assert status.managed_files == 3
    assert status.source_version == "v1"
