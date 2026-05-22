from __future__ import annotations

import pytest
from astrbot_plugin_rsshub.src.infrastructure.persistence.database import (
    DatabaseManager,
)
from astrbot_plugin_rsshub.src.infrastructure.persistence.migrations import (
    MigrationRunner,
    cleanup_legacy_translation_tables,
    ensure_push_history_schema,
)
from sqlalchemy.ext.asyncio import create_async_engine


def test_database_is_initialized_requires_session_maker():
    db = DatabaseManager()
    db._engine = object()
    db._session_maker = None

    assert db.is_initialized is False


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, columns):
        self.columns = columns
        self.executed = []

    async def exec_driver_sql(self, sql, params=None):
        self.executed.append((sql, params))
        if "sqlite_master" in sql:
            if params and params[0] in {
                "rsshub_translation_cache",
                "rsshub_translate_cache",
                "rsshub_translation_history",
                "rsshub_translate_history",
            }:
                return _Result([])
            return _Result([("rsshub_push_history",)])
        if "PRAGMA table_info" in sql:
            return _Result([(0, col, "", 0, None, 0) for col in self.columns])
        return _Result([])


@pytest.mark.asyncio
async def test_ensure_push_history_schema_adds_missing_columns():
    conn = _Conn(columns=["id", "sub_id", "user_id", "feed_id"])

    applied = await ensure_push_history_schema(conn)

    assert applied == ["source_type", "source_key", "raw_xml", "handler_trace"]
    executed_sql = "\n".join(sql for sql, _ in conn.executed)
    assert "ADD COLUMN source_type" in executed_sql
    assert "ADD COLUMN source_key" in executed_sql
    assert "ADD COLUMN raw_xml" in executed_sql
    assert "ADD COLUMN handler_trace" in executed_sql


class _LegacyTableConn(_Conn):
    def __init__(self, existing_tables):
        super().__init__(columns=[])
        self.existing_tables = set(existing_tables)

    async def exec_driver_sql(self, sql, params=None):
        self.executed.append((sql, params))
        if "sqlite_master" in sql:
            table = params[0] if params else None
            if table in self.existing_tables:
                return _Result([(table,)])
            return _Result([])
        return _Result([])


@pytest.mark.asyncio
async def test_cleanup_legacy_translation_tables_drops_existing_tables():
    conn = _LegacyTableConn(
        {
            "rsshub_translation_cache",
            "rsshub_translate_history",
        }
    )

    dropped = await cleanup_legacy_translation_tables(conn)

    assert dropped == [
        "rsshub_translation_cache",
        "rsshub_translate_history",
    ]
    executed_sql = "\n".join(sql for sql, _ in conn.executed)
    assert "DROP TABLE IF EXISTS rsshub_translation_cache" in executed_sql
    assert "DROP TABLE IF EXISTS rsshub_translate_history" in executed_sql


@pytest.mark.asyncio
async def test_migration_runner_only_discovers_current_baseline_migration():
    runner = MigrationRunner()

    assert [(item.version, item.name) for item in runner.scripts] == [(1, "V1_init")]


@pytest.mark.asyncio
async def test_v1_current_baseline_has_expected_core_columns_and_index():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        executed = await MigrationRunner().run_all(conn)

        assert executed == [1]

        sub_columns = {
            str(row[1])
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info(rsshub_sub)")
            ).fetchall()
        }
        user_columns = {
            str(row[1])
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info(rsshub_user)")
            ).fetchall()
        }
        history_columns = {
            str(row[1])
            for row in (
                await conn.exec_driver_sql("PRAGMA table_info(rsshub_push_history)")
            ).fetchall()
        }
        indexes = {
            str(row[0])
            for row in (
                await conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            ).fetchall()
        }

        assert "handlers_mode" in sub_columns
        assert "handlers_mode" not in user_columns
        assert "link_preview" not in user_columns
        assert "link_preview" not in sub_columns
        assert {"source_type", "source_key", "raw_xml", "handler_trace"}.issubset(
            history_columns
        )
        assert "idx_rsshub_push_history_scope_guid" in indexes

    await engine.dispose()
