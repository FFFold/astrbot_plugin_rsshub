from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_rsshub.src.domain.entities.feed import Feed
from astrbot_plugin_rsshub.src.infrastructure.persistence.feed_repository_impl import (
    FeedRepositoryImpl,
)


class _DummySession:
    def __init__(self, existing=None):
        self._existing = existing
        self.add = MagicMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()

    async def get(self, model, feed_id):
        return self._existing


class _DummyCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_save_updates_existing_without_insert(monkeypatch):
    existing = MagicMock()
    existing.id = 1
    existing.state = 0
    existing.link = "https://old"
    existing.title = "old"
    existing.entry_hashes = None
    existing.etag = None
    existing.last_modified = None
    existing.created_at = datetime.now(timezone.utc)
    existing.updated_at = datetime.now(timezone.utc)

    session = _DummySession(existing=existing)
    db = MagicMock()
    db.get_session.return_value = _DummyCtx(session)

    monkeypatch.setattr(
        "astrbot_plugin_rsshub.src.infrastructure.persistence.feed_repository_impl.get_database",
        lambda: db,
    )

    repo = FeedRepositoryImpl()
    feed = Feed(id=1, state=1, link="https://new", title="new")

    saved = await repo.save(feed)

    session.add.assert_not_called()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(existing)
    assert saved.id == 1
    assert saved.link == "https://new"
    assert saved.title == "new"
