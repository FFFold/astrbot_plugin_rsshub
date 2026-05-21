from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest
from astrbot_plugin_rsshub.src.application.ports.route_knowledge import (
    RouteKnowledgeDocument,
    RouteKnowledgeDocumentRecord,
    RouteKnowledgeFile,
    RouteKnowledgeManifest,
)
from astrbot_plugin_rsshub.src.application.services.route_knowledge_service import (
    RouteKnowledgeSyncAlreadyRunning,
    RouteKnowledgeSyncService,
    build_route_knowledge_prompt,
    build_sync_plan,
    managed_doc_name,
    should_inject_route_knowledge_prompt,
)
from astrbot_plugin_rsshub.src.application.settings import RouteKnowledgeSettings


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class _StoredDoc:
    doc_id: str
    doc_name: str
    content: str


class _FakeSource:
    def __init__(self, files: dict[str, str]):
        self.files = files
        self.closed = False

    async def fetch_manifest(self):
        return RouteKnowledgeManifest(
            files=tuple(
                RouteKnowledgeFile(path=path, sha256=_sha(content))
                for path, content in self.files.items()
            ),
            version="v1",
            generated_at="2026-05-19T00:00:00Z",
        )

    async def fetch_document(self, file):
        return RouteKnowledgeDocument(
            path=file.path,
            content=self.files[file.path],
            sha256=file.sha256,
        )

    async def close(self):
        self.closed = True


class _BadHashSource(_FakeSource):
    async def fetch_document(self, file):
        return RouteKnowledgeDocument(
            path=file.path,
            content="tampered",
            sha256=file.sha256,
        )


class _FakeRepository:
    def __init__(self):
        self.docs: dict[str, _StoredDoc] = {}
        self.deleted: list[str] = []
        self.uploaded: list[str] = []

    async def ensure_kb(self):
        return "kb-1"

    async def list_documents(self):
        return [
            RouteKnowledgeDocumentRecord(doc_id=doc.doc_id, doc_name=doc.doc_name)
            for doc in self.docs.values()
        ]

    async def delete_document(self, doc_id: str):
        self.deleted.append(doc_id)
        self.docs.pop(doc_id, None)

    async def upload_document(self, document):
        doc_id = f"doc-{len(self.docs) + len(self.uploaded) + 1}"
        doc_name = managed_doc_name(document.path)
        self.docs[doc_id] = _StoredDoc(doc_id, doc_name, document.content)
        self.uploaded.append(doc_name)
        return doc_id


class _FlakyUploadRepository(_FakeRepository):
    def __init__(self, fail_path: str):
        super().__init__()
        self.fail_path = fail_path

    async def upload_document(self, document):
        if document.path == self.fail_path:
            raise RuntimeError("boom")
        return await super().upload_document(document)


def test_build_sync_plan_detects_add_update_delete_unchanged():
    source = RouteKnowledgeManifest(
        files=(
            RouteKnowledgeFile(path="index/namespaces.md", sha256="a"),
            RouteKnowledgeFile(path="docs/routes/foo.md", sha256="b2"),
            RouteKnowledgeFile(path="docs/routes/bar.md", sha256="c"),
        )
    )
    local = {
        "files": [
            {"path": "index/namespaces.md", "sha256": "a"},
            {"path": "docs/routes/foo.md", "sha256": "b1"},
            {"path": "docs/routes/deleted.md", "sha256": "d"},
        ]
    }

    plan = build_sync_plan(source, local)

    assert [item.path for item in plan.added] == ["docs/routes/bar.md"]
    assert [item.path for item in plan.updated] == ["docs/routes/foo.md"]
    assert plan.deleted == ("docs/routes/deleted.md",)
    assert [item.path for item in plan.unchanged] == ["index/namespaces.md"]


@pytest.mark.asyncio
async def test_sync_deletes_then_uploads_changed_documents(tmp_path):
    source = _FakeSource(
        {
            "index/namespaces.md": "# Namespaces",
            "docs/routes/foo.md": "# Foo v2",
        }
    )
    repo = _FakeRepository()
    old_doc_id = "old-doc"
    repo.docs[old_doc_id] = _StoredDoc(
        old_doc_id,
        managed_doc_name("docs/routes/foo.md"),
        "# Foo v1",
    )
    (tmp_path / "manifest.json").write_text(
        '{"files":[{"path":"docs/routes/foo.md","sha256":"old"},'
        '{"path":"docs/routes/deleted.md","sha256":"gone"}]}',
        encoding="utf-8",
    )
    service = RouteKnowledgeSyncService(
        settings=RouteKnowledgeSettings(),
        source=source,
        repository=repo,
        state_dir=tmp_path,
    )

    result = await service.sync(task_id="task-1")

    assert result.success is True
    assert old_doc_id in repo.deleted
    assert managed_doc_name("docs/routes/foo.md") in repo.uploaded
    assert managed_doc_name("index/namespaces.md") in repo.uploaded
    status = service.get_task_status()
    assert status.status == "completed"
    assert status.added == 1
    assert status.updated == 1
    assert status.deleted == 1


@pytest.mark.asyncio
async def test_sync_skips_failed_document_and_continues(tmp_path):
    source = _FakeSource(
        {
            "docs/routes/a.md": "# A",
            "docs/routes/b.md": "# B",
        }
    )
    repo = _FlakyUploadRepository("docs/routes/a.md")
    service = RouteKnowledgeSyncService(
        settings=RouteKnowledgeSettings(),
        source=source,
        repository=repo,
        state_dir=tmp_path,
    )

    result = await service.sync(task_id="task-1")

    assert result.success is True
    assert result.skipped == 1
    assert managed_doc_name("docs/routes/b.md") in repo.uploaded
    assert managed_doc_name("docs/routes/a.md") not in repo.uploaded
    assert service.get_task_status().skipped == 1


@pytest.mark.asyncio
async def test_sync_rejects_sha256_mismatch(tmp_path):
    source = _BadHashSource({"docs/routes/foo.md": "# Foo"})
    repo = _FakeRepository()
    service = RouteKnowledgeSyncService(
        settings=RouteKnowledgeSettings(),
        source=source,
        repository=repo,
        state_dir=tmp_path,
    )

    result = await service.sync(task_id="task-1")

    assert result.success is False
    assert "sha256 校验失败" in result.message
    assert service.get_task_status().status == "failed"
    assert repo.uploaded == []


@pytest.mark.asyncio
async def test_sync_lock_rejects_parallel_runs(tmp_path):
    source = _FakeSource({"docs/routes/foo.md": "# Foo"})
    repo = _FakeRepository()
    service = RouteKnowledgeSyncService(
        settings=RouteKnowledgeSettings(),
        source=source,
        repository=repo,
        state_dir=tmp_path,
    )

    await service._lock.acquire()
    try:
        with pytest.raises(RouteKnowledgeSyncAlreadyRunning):
            await service.sync(task_id="task-2")
    finally:
        service._lock.release()


def test_route_intent_prompt_injection_guard():
    assert should_inject_route_knowledge_prompt("帮我查 RSSHub 的 bilibili 路由")
    assert should_inject_route_knowledge_prompt("如何订阅 x 用户动态 rsshub")
    assert not should_inject_route_knowledge_prompt("今天 RSS 新闻是什么")
    assert "astr_kb_search" in build_route_knowledge_prompt("RSSHub Routes")
