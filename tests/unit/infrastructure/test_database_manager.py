from __future__ import annotations

import pytest
from astrbot_plugin_rsshub.src.infrastructure.persistence.database import (
    DatabaseManager,
)
from astrbot_plugin_rsshub.src.infrastructure.persistence.migrations import (
    cleanup_legacy_translation_tables,
    ensure_push_history_schema,
    ensure_user_subscription_prompt_schema,
)
from astrbot_plugin_rsshub.src.infrastructure.persistence.migrations.V6_ai_prompt_and_inherit_options import (
    upgrade as upgrade_v6,
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

    assert applied == ["source_type", "source_key", "raw_xml"]
    executed_sql = "\n".join(sql for sql, _ in conn.executed)
    assert "ADD COLUMN source_type" in executed_sql
    assert "ADD COLUMN source_key" in executed_sql
    assert "ADD COLUMN raw_xml" in executed_sql


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


async def _columns(conn, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in result.fetchall()}


@pytest.mark.asyncio
async def test_v6_rebuilds_user_and_sub_tables_for_ai_prompt_and_inherit_fields():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY,
                state INTEGER NOT NULL DEFAULT 1,
                interval INTEGER,
                notify INTEGER NOT NULL DEFAULT 1,
                send_mode INTEGER NOT NULL DEFAULT 0,
                length_limit INTEGER NOT NULL DEFAULT 0,
                link_preview INTEGER NOT NULL DEFAULT 0,
                display_author INTEGER NOT NULL DEFAULT 0,
                display_via INTEGER NOT NULL DEFAULT 0,
                display_title INTEGER NOT NULL DEFAULT 0,
                display_entry_tags INTEGER NOT NULL DEFAULT -1,
                style INTEGER NOT NULL DEFAULT 0,
                display_media INTEGER NOT NULL DEFAULT 0,
                default_target_session TEXT,
                needs_binding_notice INTEGER NOT NULL DEFAULT 0,
                use_user_config INTEGER NOT NULL DEFAULT 0,
                translate INTEGER,
                translate_target_lang TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_feed (
                id INTEGER PRIMARY KEY,
                state INTEGER NOT NULL DEFAULT 1,
                link VARCHAR(4096) NOT NULL UNIQUE,
                title VARCHAR(1024) NOT NULL
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_sub (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state INTEGER NOT NULL DEFAULT 1,
                user_id VARCHAR NOT NULL,
                feed_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                target_session TEXT,
                platform_name TEXT,
                interval INTEGER,
                next_check_time DATETIME,
                notify INTEGER NOT NULL DEFAULT -100,
                send_mode INTEGER NOT NULL DEFAULT -100,
                length_limit INTEGER NOT NULL DEFAULT -100,
                link_preview INTEGER NOT NULL DEFAULT -100,
                display_author INTEGER NOT NULL DEFAULT -100,
                display_via INTEGER NOT NULL DEFAULT -100,
                display_title INTEGER NOT NULL DEFAULT -100,
                display_entry_tags INTEGER NOT NULL DEFAULT -100,
                style INTEGER NOT NULL DEFAULT -100,
                display_media INTEGER NOT NULL DEFAULT -100,
                use_sub_config INTEGER NOT NULL DEFAULT 0,
                translate INTEGER,
                translate_target_lang TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES rsshub_user (id),
                FOREIGN KEY (feed_id) REFERENCES rsshub_feed (id)
            )
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO rsshub_user (
                id, interval, notify, send_mode, length_limit, link_preview,
                display_author, display_via, display_title, display_entry_tags,
                style, display_media, use_user_config, translate
            )
            VALUES ('u1', 15, 0, 2, 500, 1, -1, -2, -1, 0, 1, -1, 1, 1)
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO rsshub_user (
                id, interval, notify, send_mode, length_limit, link_preview,
                display_author, display_via, display_title, display_entry_tags,
                style, display_media, use_user_config, translate
            )
            VALUES ('u2', 20, 1, 0, 300, 0, 0, 0, 0, -1, 0, 0, 0, 1)
            """
        )
        await conn.exec_driver_sql(
            "INSERT INTO rsshub_feed (id, link, title) VALUES (1, 'https://example.com/rss', 'Feed')"
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO rsshub_sub (
                id, user_id, feed_id, interval, notify, send_mode,
                length_limit, link_preview, display_author, display_via,
                display_title, display_entry_tags, style, display_media,
                use_sub_config, translate
            )
            VALUES (1, 'u1', 1, 15, 0, 2, 500, 1, -1, -2, -1, 0, 1, -1, 1, 1)
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO rsshub_sub (
                id, user_id, feed_id, interval, notify, send_mode,
                length_limit, link_preview, display_author, display_via,
                display_title, display_entry_tags, style, display_media,
                use_sub_config, translate
            )
            VALUES (2, 'u1', 1, 20, 1, 0, 300, 0, 0, 0, 0, -1, 0, 0, 0, 1)
            """
        )

        await upgrade_v6(conn)

        user_columns = await _columns(conn, "rsshub_user")
        sub_columns = await _columns(conn, "rsshub_sub")

        assert "ai_prompt" in user_columns
        assert "ai_prompt" in sub_columns
        assert "use_user_config" not in user_columns
        assert "use_sub_config" not in sub_columns
        assert "translate" not in user_columns
        assert "translate_target_lang" not in sub_columns

        user_row = (
            await conn.exec_driver_sql(
                """
                SELECT
                    id, interval, notify, send_mode, ai_prompt, length_limit,
                    link_preview, display_author, display_via, display_title,
                    display_entry_tags, style, display_media
                FROM rsshub_user ORDER BY id
                """
            )
        ).fetchall()
        sub_rows = (
            await conn.exec_driver_sql(
                """
                SELECT
                    id, interval, notify, send_mode, ai_prompt, length_limit,
                    link_preview, display_author, display_via, display_title,
                    display_entry_tags, style, display_media
                FROM rsshub_sub ORDER BY id
                """
            )
        ).fetchall()
        assert user_row == [
            ("u1", 15, 0, 2, "", 500, 1, -1, -2, -1, 0, 1, -1),
            ("u2", -100, -100, -100, "", -100, -100, -100, -100, -100, -100, -100, -100),
        ]
        assert sub_rows == [
            (1, 15, 0, 2, "", 500, 1, -1, -2, -1, 0, 1, -1),
            (2, -100, -100, -100, "", -100, -100, -100, -100, -100, -100, -100, -100),
        ]

    await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_schema_self_heal_runs_v6_rebuild_logic():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY,
                use_user_config INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        changed = await ensure_user_subscription_prompt_schema(conn)

        assert changed == ["rsshub_user"]
        columns = await _columns(conn, "rsshub_user")
        assert "handlers" in columns
        assert "use_user_config" not in columns

    await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_schema_self_heal_rebuilds_user_table_default_values():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY,
                state INTEGER NOT NULL DEFAULT 1,
                interval INTEGER,
                notify INTEGER NOT NULL DEFAULT 1,
                send_mode INTEGER NOT NULL DEFAULT 0,
                ai_prompt TEXT NOT NULL DEFAULT '',
                length_limit INTEGER NOT NULL DEFAULT 0,
                link_preview INTEGER NOT NULL DEFAULT 0,
                display_author INTEGER NOT NULL DEFAULT 0,
                display_via INTEGER NOT NULL DEFAULT 0,
                display_title INTEGER NOT NULL DEFAULT 0,
                display_entry_tags INTEGER NOT NULL DEFAULT -1,
                style INTEGER NOT NULL DEFAULT 0,
                display_media INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        changed = await ensure_user_subscription_prompt_schema(conn)

        assert changed == ["rsshub_user"]
        result = await conn.exec_driver_sql("PRAGMA table_info(rsshub_user)")
        defaults = {str(row[1]): row[4] for row in result.fetchall()}
        assert defaults["notify"] == "-100"
        assert defaults["send_mode"] == "-100"
        assert defaults["length_limit"] == "-100"

    await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_schema_self_heal_rebuilds_sub_table_default_values():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_feed (
                id INTEGER PRIMARY KEY,
                link VARCHAR(4096) NOT NULL UNIQUE,
                title VARCHAR(1024) NOT NULL
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_sub (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state INTEGER NOT NULL DEFAULT 1,
                user_id VARCHAR NOT NULL,
                feed_id INTEGER NOT NULL,
                interval INTEGER,
                notify INTEGER NOT NULL DEFAULT -100,
                send_mode INTEGER NOT NULL DEFAULT -100,
                ai_prompt TEXT NOT NULL DEFAULT '',
                length_limit INTEGER NOT NULL DEFAULT -100,
                link_preview INTEGER NOT NULL DEFAULT -100,
                display_author INTEGER NOT NULL DEFAULT -100,
                display_via INTEGER NOT NULL DEFAULT -100,
                display_title INTEGER NOT NULL DEFAULT -100,
                display_entry_tags INTEGER NOT NULL DEFAULT -100,
                style INTEGER NOT NULL DEFAULT -100,
                display_media INTEGER NOT NULL DEFAULT -100
            )
            """
        )

        changed = await ensure_user_subscription_prompt_schema(conn)

        assert "rsshub_sub" in changed
        result = await conn.exec_driver_sql("PRAGMA table_info(rsshub_sub)")
        defaults = {str(row[1]): row[4] for row in result.fetchall()}
        assert defaults["interval"] == "-100"
        assert defaults["notify"] == "-100"
        assert defaults["send_mode"] == "-100"
        assert defaults["handlers_mode"] == "'inherit'"

    await engine.dispose()


@pytest.mark.asyncio
async def test_prompt_schema_self_heal_adds_handlers_mode_and_backfills_semantics():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_feed (
                id INTEGER PRIMARY KEY,
                link VARCHAR(4096) NOT NULL UNIQUE,
                title VARCHAR(1024) NOT NULL
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_sub (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state INTEGER NOT NULL DEFAULT 1,
                user_id VARCHAR NOT NULL,
                feed_id INTEGER NOT NULL,
                handlers TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.exec_driver_sql(
            """
            INSERT INTO rsshub_sub (id, user_id, feed_id, handlers)
            VALUES
                (1, 'u1', 1, '[]'),
                (2, 'u1', 1, '[{"id":"builtin.ai_transform.default"}]')
            """
        )

        changed = await ensure_user_subscription_prompt_schema(conn)

        assert "rsshub_sub" in changed
        rows = (
            await conn.exec_driver_sql(
                "SELECT id, handlers_mode FROM rsshub_sub ORDER BY id"
            )
        ).fetchall()
        assert rows == [(1, "inherit"), (2, "override")]

    await engine.dispose()
