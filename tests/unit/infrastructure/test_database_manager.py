from __future__ import annotations

from astrbot_plugin_rsshub.src.infrastructure.persistence.database import (
    DatabaseManager,
)


def test_database_is_initialized_requires_session_maker():
    db = DatabaseManager()
    db._engine = object()
    db._session_maker = None

    assert db.is_initialized is False
