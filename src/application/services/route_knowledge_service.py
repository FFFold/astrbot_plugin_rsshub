"""RSSHub Routes knowledge-base synchronization service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...infrastructure.utils import get_logger
from ..ports.route_knowledge import (
    RouteKnowledgeDocument,
    RouteKnowledgeFile,
    RouteKnowledgeManifest,
    RouteKnowledgeRepository,
    RouteKnowledgeSource,
)
from ..settings import RouteKnowledgeSettings

MANAGED_DOC_PREFIX = "rsshub-routes/"
logger = get_logger()


@dataclass(frozen=True)
class RouteKnowledgeSyncPlan:
    """Diff between source manifest and local managed manifest."""

    added: tuple[RouteKnowledgeFile, ...] = field(default_factory=tuple)
    updated: tuple[RouteKnowledgeFile, ...] = field(default_factory=tuple)
    deleted: tuple[str, ...] = field(default_factory=tuple)
    unchanged: tuple[RouteKnowledgeFile, ...] = field(default_factory=tuple)

    @property
    def changed_count(self) -> int:
        return len(self.added) + len(self.updated) + len(self.deleted)


@dataclass(frozen=True)
class RouteKnowledgeTaskStatus:
    """Current or last background sync task status."""

    task_id: str = ""
    status: str = "idle"
    kb_name: str = ""
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    error: str = ""
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    skipped: int = 0
    processed: int = 0
    total: int = 0
    current_path: str = ""


@dataclass(frozen=True)
class RouteKnowledgeStatus:
    """Routes KB sync status snapshot."""

    kb_name: str
    kb_id: str = ""
    source_version: str = ""
    source_generated_at: str = ""
    last_sync_at: str = ""
    managed_files: int = 0
    kb_docs: int = 0
    last_error: str = ""
    task: RouteKnowledgeTaskStatus = field(default_factory=RouteKnowledgeTaskStatus)


@dataclass(frozen=True)
class RouteKnowledgeSyncResult:
    """Completed sync result."""

    success: bool
    message: str
    task_id: str
    plan: RouteKnowledgeSyncPlan
    uploaded: int = 0
    deleted: int = 0
    skipped: int = 0
    kb_id: str = ""


class RouteKnowledgeSyncAlreadyRunning(RuntimeError):
    """Raised when a sync is requested while another sync is running."""


class RouteKnowledgeSyncService:
    """Synchronize RSSHub route markdown files into an AstrBot knowledge base."""

    def __init__(
        self,
        *,
        settings: RouteKnowledgeSettings,
        source: RouteKnowledgeSource,
        repository: RouteKnowledgeRepository,
        state_dir: Path,
    ) -> None:
        self._settings = settings
        self._source = source
        self._repository = repository
        self._state_dir = state_dir
        self._manifest_path = state_dir / "manifest.json"
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[RouteKnowledgeSyncResult] | None = None
        self._task_status = RouteKnowledgeTaskStatus(kb_name=settings.kb_name)

    async def close(self) -> None:
        await self._source.close()

    async def ensure_kb(self) -> str:
        return await self._repository.ensure_kb()

    def get_task_status(self) -> RouteKnowledgeTaskStatus:
        return self._task_status

    async def get_status(self) -> RouteKnowledgeStatus:
        local = self._load_local_manifest()
        kb_id = ""
        kb_docs = 0
        last_error = ""
        try:
            kb_id = await self._repository.ensure_kb()
            kb_docs = len(await self._repository.list_documents())
        except Exception as exc:
            last_error = str(exc)
        if self._task_status.error:
            last_error = self._task_status.error
        return RouteKnowledgeStatus(
            kb_name=self._settings.kb_name,
            kb_id=kb_id,
            source_version=str(local.get("version", "") or ""),
            source_generated_at=str(local.get("generated_at", "") or ""),
            last_sync_at=str(local.get("last_sync_at", "") or ""),
            managed_files=len(_local_files_map(local)),
            kb_docs=kb_docs,
            last_error=last_error,
            task=self._task_status,
        )

    async def start_sync(self) -> RouteKnowledgeTaskStatus:
        if self._task is not None and not self._task.done():
            raise RouteKnowledgeSyncAlreadyRunning("Routes KB 同步任务正在运行")
        task_id = uuid.uuid4().hex[:12]
        self._task_status = RouteKnowledgeTaskStatus(
            task_id=task_id,
            status="queued",
            kb_name=self._settings.kb_name,
            started_at=_now_iso(),
            message="等待同步",
        )
        self._task = asyncio.create_task(self.sync(task_id=task_id))
        return self._task_status

    async def sync(self, *, task_id: str | None = None) -> RouteKnowledgeSyncResult:
        if self._lock.locked():
            raise RouteKnowledgeSyncAlreadyRunning("Routes KB 同步任务正在运行")
        async with self._lock:
            effective_task_id = task_id or uuid.uuid4().hex[:12]
            started_at = _now_iso()
            logger.info(
                "Routes KB 同步开始: task_id=%s kb_name=%s",
                effective_task_id,
                self._settings.kb_name,
            )
            self._task_status = RouteKnowledgeTaskStatus(
                task_id=effective_task_id,
                status="running",
                kb_name=self._settings.kb_name,
                started_at=started_at,
                message="读取 metadata.json",
            )
            try:
                kb_id = await self._repository.ensure_kb()
                logger.info(
                    "Routes KB 已确认知识库: task_id=%s kb_id=%s",
                    effective_task_id,
                    kb_id or "-",
                )
                source_manifest = await self._source.fetch_manifest()
                logger.info(
                    "Routes KB 已读取源 manifest: task_id=%s version=%s files=%d",
                    effective_task_id,
                    source_manifest.version,
                    len(source_manifest.files),
                )
                local_manifest = self._load_local_manifest()
                plan = build_sync_plan(source_manifest, local_manifest)
                total = len(plan.added) + len(plan.updated) + len(plan.deleted)
                logger.info(
                    "Routes KB 同步计划: task_id=%s added=%d updated=%d deleted=%d unchanged=%d total=%d",
                    effective_task_id,
                    len(plan.added),
                    len(plan.updated),
                    len(plan.deleted),
                    len(plan.unchanged),
                    total,
                )
                self._task_status = _replace_task(
                    self._task_status,
                    message="同步文档",
                    added=len(plan.added),
                    updated=len(plan.updated),
                    deleted=len(plan.deleted),
                    unchanged=len(plan.unchanged),
                    skipped=0,
                    total=total,
                )

                docs_by_name = {
                    doc.doc_name: doc.doc_id
                    for doc in await self._repository.list_documents()
                }
                uploaded_count = 0
                deleted_count = 0
                skipped_count = 0
                processed = 0

                for path in plan.deleted:
                    doc_name = managed_doc_name(path)
                    doc_id = docs_by_name.get(doc_name)
                    self._task_status = _replace_task(
                        self._task_status,
                        current_path=path,
                        processed=processed,
                        message="删除已移除文档",
                    )
                    logger.info(
                        "Routes KB 同步进度: task_id=%s %d/%d 删除 %s",
                        effective_task_id,
                        processed + 1,
                        total or 1,
                        path,
                    )
                    if doc_id:
                        await self._repository.delete_document(doc_id)
                        deleted_count += 1
                    processed += 1
                    self._task_status = _replace_task(
                        self._task_status, processed=processed
                    )

                for file in (*plan.added, *plan.updated):
                    doc_name = managed_doc_name(file.path)
                    old_doc_id = docs_by_name.get(doc_name)
                    self._task_status = _replace_task(
                        self._task_status,
                        current_path=file.path,
                        processed=processed,
                        message="上传文档",
                    )
                    logger.info(
                        "Routes KB 同步进度: task_id=%s %d/%d 上传 %s",
                        effective_task_id,
                        processed + 1,
                        total or 1,
                        file.path,
                    )
                    document = await self._source.fetch_document(file)
                    _validate_document_hash(file, document)
                    try:
                        if old_doc_id:
                            await self._repository.delete_document(old_doc_id)
                        await self._repository.upload_document(document)
                        uploaded_count += 1
                    except Exception as exc:
                        skipped_count += 1
                        logger.exception(
                            "Routes KB 文档上传失败，已跳过: task_id=%s path=%s error=%s",
                            effective_task_id,
                            file.path,
                            exc,
                        )
                        self._task_status = _replace_task(
                            self._task_status,
                            skipped=skipped_count,
                            message=f"跳过失败文档: {file.path}",
                        )
                    processed += 1
                    self._task_status = _replace_task(
                        self._task_status, processed=processed
                    )

                self._write_local_manifest(source_manifest)
                message = (
                    "Routes KB 同步完成: "
                    f"新增 {len(plan.added)}, 更新 {len(plan.updated)}, "
                    f"删除 {deleted_count}, 跳过 {skipped_count}, 未变更 {len(plan.unchanged)}"
                )
                finished_at = _now_iso()
                logger.info(
                    "Routes KB 同步完成: task_id=%s kb_id=%s 新增=%d 更新=%d 删除=%d 跳过=%d 未变更=%d",
                    effective_task_id,
                    kb_id or "-",
                    len(plan.added),
                    len(plan.updated),
                    deleted_count,
                    skipped_count,
                    len(plan.unchanged),
                )
                self._task_status = _replace_task(
                    self._task_status,
                    status="completed",
                    finished_at=finished_at,
                    message=message,
                    current_path="",
                    processed=total,
                    skipped=skipped_count,
                )
                return RouteKnowledgeSyncResult(
                    success=True,
                    message=message,
                    task_id=effective_task_id,
                    plan=plan,
                    uploaded=uploaded_count,
                    deleted=deleted_count,
                    skipped=skipped_count,
                    kb_id=kb_id,
                )
            except Exception as exc:
                logger.exception(
                    "Routes KB 同步失败: task_id=%s kb_name=%s error=%s",
                    effective_task_id,
                    self._settings.kb_name,
                    exc,
                )
                self._task_status = _replace_task(
                    self._task_status,
                    status="failed",
                    finished_at=_now_iso(),
                    error=str(exc),
                    message="Routes KB 同步失败",
                )
                empty_plan = RouteKnowledgeSyncPlan()
                return RouteKnowledgeSyncResult(
                    success=False,
                    message=f"Routes KB 同步失败: {exc}",
                    task_id=effective_task_id,
                    plan=empty_plan,
                )

    def _load_local_manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            return {}
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def _write_local_manifest(self, manifest: RouteKnowledgeManifest) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": manifest.version,
            "generated_at": manifest.generated_at,
            "source": manifest.source,
            "last_sync_at": _now_iso(),
            "files": [asdict(file) for file in manifest.files],
        }
        self._manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def build_sync_plan(
    source_manifest: RouteKnowledgeManifest,
    local_manifest: dict[str, Any],
) -> RouteKnowledgeSyncPlan:
    """Build an incremental sync plan by comparing path + sha256."""
    source_files = {file.path: file for file in source_manifest.files}
    local_files = _local_files_map(local_manifest)

    added: list[RouteKnowledgeFile] = []
    updated: list[RouteKnowledgeFile] = []
    unchanged: list[RouteKnowledgeFile] = []

    for path, file in source_files.items():
        local_sha = local_files.get(path)
        if local_sha is None:
            added.append(file)
        elif local_sha != file.sha256:
            updated.append(file)
        else:
            unchanged.append(file)

    deleted = sorted(path for path in local_files if path not in source_files)
    return RouteKnowledgeSyncPlan(
        added=tuple(sorted(added, key=lambda item: item.path)),
        updated=tuple(sorted(updated, key=lambda item: item.path)),
        deleted=tuple(deleted),
        unchanged=tuple(sorted(unchanged, key=lambda item: item.path)),
    )


def should_inject_route_knowledge_prompt(text: str) -> bool:
    """Return True when user text looks like an RSSHub route lookup request."""
    normalized = (text or "").lower()
    if not normalized.strip():
        return False
    route_markers = (
        "rsshub",
        "rss hub",
        "路由",
        "订阅源",
        "订阅链接",
        "rss 链接",
        "rss链接",
        "feed url",
        "feed 地址",
        "feed地址",
    )
    intent_markers = (
        "怎么订阅",
        "如何订阅",
        "帮我订阅",
        "订阅",
        "构建",
        "生成",
        "查",
        "找",
        "搜索",
        "route",
        "feed",
    )
    return any(marker in normalized for marker in route_markers) and any(
        marker in normalized for marker in intent_markers
    )


def build_route_knowledge_prompt(kb_name: str) -> str:
    """Instruction injected only for RSSHub route lookup intent."""
    return (
        "RSSHub 路由查询提示：当用户想查找 RSSHub 路由或生成订阅链接时，"
        f"先确认 AstrBot 知识库配置已启用 `{kb_name}`，"
        "再使用 AstrBot 知识库工具 astr_kb_search 查询路由文档；"
        "根据查到的 URI 和参数说明直接整理出订阅 URL；"
        "用户明确要订阅时，再调用 rss_subscribe。不要臆造不存在的路由参数。"
    )


def managed_doc_name(path: str) -> str:
    return f"{MANAGED_DOC_PREFIX}{path.strip().lstrip('/')}"


def _validate_document_hash(
    file: RouteKnowledgeFile, document: RouteKnowledgeDocument
) -> None:
    digest = hashlib.sha256(document.content.encode("utf-8")).hexdigest()
    if digest != file.sha256:
        raise ValueError(
            f"sha256 校验失败: {file.path} expected={file.sha256} actual={digest}"
        )


def _local_files_map(local_manifest: dict[str, Any]) -> dict[str, str]:
    raw_files = local_manifest.get("files", [])
    files: dict[str, str] = {}
    if isinstance(raw_files, dict):
        iterable = raw_files.items()
        for path, item in iterable:
            if isinstance(item, dict):
                sha = item.get("sha256") or item.get("sha")
            else:
                sha = item
            if path and sha:
                files[str(path)] = str(sha)
        return files
    if isinstance(raw_files, list):
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or item.get("name")
            sha = item.get("sha256") or item.get("sha")
            if path and sha:
                files[str(path)] = str(sha)
    return files


def _replace_task(
    current: RouteKnowledgeTaskStatus, **updates: Any
) -> RouteKnowledgeTaskStatus:
    data = asdict(current)
    data.update(updates)
    return RouteKnowledgeTaskStatus(**data)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
