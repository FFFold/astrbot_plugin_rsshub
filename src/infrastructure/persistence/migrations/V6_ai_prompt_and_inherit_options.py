"""V6 add AI prompt fields and remove legacy config flags."""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def _table_exists(conn, table: str) -> bool:
    result = await conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return result.fetchone() is not None


async def _column_names(conn, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in result.fetchall()}


def _select_expr(columns: set[str], column: str, default_sql: str) -> str:
    return column if column in columns else default_sql


async def _column_default_map(conn, table: str) -> dict[str, object]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {str(row[1]): row[4] for row in result.fetchall()}


def _sqlite_default_is(value: object, expected: str) -> bool:
    if value == int(expected):
        return True
    return str(value).strip("'\"") == expected


def _legacy_user_option_expr(
    columns: set[str],
    column: str,
    enabled_default_sql: str,
    inherit_default_sql: str = "-100",
) -> str:
    if "use_user_config" not in columns:
        return f"COALESCE({_select_expr(columns, column, inherit_default_sql)}, {inherit_default_sql})"
    value_expr = _select_expr(columns, column, enabled_default_sql)
    return (
        "CASE WHEN COALESCE(use_user_config, 0) = 0 "
        f"THEN {inherit_default_sql} "
        f"ELSE COALESCE({value_expr}, {enabled_default_sql}) END"
    )


def _legacy_sub_option_expr(
    columns: set[str],
    column: str,
    enabled_default_sql: str,
    inherit_default_sql: str = "-100",
) -> str:
    if "use_sub_config" not in columns:
        return f"COALESCE({_select_expr(columns, column, inherit_default_sql)}, {inherit_default_sql})"
    value_expr = _select_expr(columns, column, enabled_default_sql)
    return (
        "CASE WHEN COALESCE(use_sub_config, 0) = 0 "
        f"THEN {inherit_default_sql} "
        f"ELSE COALESCE({value_expr}, {enabled_default_sql}) END"
    )


async def _rebuild_user_table(conn) -> None:
    if not await _table_exists(conn, "rsshub_user"):
        return

    columns = await _column_names(conn, "rsshub_user")
    legacy_columns = {
        "use_user_config",
        "translate",
        "translate_target_lang",
    }
    if "ai_prompt" in columns and not legacy_columns.intersection(columns):
        defaults = await _column_default_map(conn, "rsshub_user")
        inherit_columns = {
            "interval",
            "notify",
            "send_mode",
            "length_limit",
            "link_preview",
            "display_author",
            "display_via",
            "display_title",
            "display_entry_tags",
            "style",
            "display_media",
        }
        if all(
            _sqlite_default_is(defaults.get(column), "-100")
            for column in inherit_columns
        ):
            return

    await conn.exec_driver_sql(
        """
        CREATE TABLE rsshub_user__new (
            id VARCHAR PRIMARY KEY,
            state INTEGER NOT NULL DEFAULT 1,
            interval INTEGER NOT NULL DEFAULT -100,
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
            display_media INTEGER NOT NULL DEFAULT -100,
            default_target_session TEXT,
            needs_binding_notice INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await conn.exec_driver_sql(
        f"""
        INSERT INTO rsshub_user__new (
            id, state, interval, notify, send_mode, ai_prompt, length_limit,
            link_preview, display_author, display_via, display_title,
            display_entry_tags, style, display_media, default_target_session,
            needs_binding_notice, created_at, updated_at
        )
        SELECT
            id,
            COALESCE({_select_expr(columns, "state", "1")}, 1),
            {_legacy_user_option_expr(columns, "interval", "10")},
            {_legacy_user_option_expr(columns, "notify", "1")},
            {_legacy_user_option_expr(columns, "send_mode", "0")},
            COALESCE({_select_expr(columns, "ai_prompt", "''")}, ''),
            {_legacy_user_option_expr(columns, "length_limit", "0")},
            {_legacy_user_option_expr(columns, "link_preview", "0")},
            {_legacy_user_option_expr(columns, "display_author", "0")},
            {_legacy_user_option_expr(columns, "display_via", "0")},
            {_legacy_user_option_expr(columns, "display_title", "0")},
            {_legacy_user_option_expr(columns, "display_entry_tags", "-1")},
            {_legacy_user_option_expr(columns, "style", "0")},
            {_legacy_user_option_expr(columns, "display_media", "0")},
            {_select_expr(columns, "default_target_session", "NULL")},
            COALESCE({_select_expr(columns, "needs_binding_notice", "0")}, 0),
            COALESCE({_select_expr(columns, "created_at", "CURRENT_TIMESTAMP")}, CURRENT_TIMESTAMP),
            COALESCE({_select_expr(columns, "updated_at", "CURRENT_TIMESTAMP")}, CURRENT_TIMESTAMP)
        FROM rsshub_user
        """
    )
    await conn.exec_driver_sql("DROP TABLE rsshub_user")
    await conn.exec_driver_sql("ALTER TABLE rsshub_user__new RENAME TO rsshub_user")
    logger.info("迁移 V6: 重建 rsshub_user，添加 ai_prompt 并移除旧配置/翻译字段")


async def _rebuild_sub_table(conn) -> None:
    if not await _table_exists(conn, "rsshub_sub"):
        return

    columns = await _column_names(conn, "rsshub_sub")
    legacy_columns = {
        "use_sub_config",
        "translate",
        "translate_target_lang",
    }
    inherit_columns = {
        "interval",
        "notify",
        "send_mode",
        "length_limit",
        "link_preview",
        "display_author",
        "display_via",
        "display_title",
        "display_entry_tags",
        "style",
        "display_media",
    }
    if "ai_prompt" in columns and not legacy_columns.intersection(columns):
        defaults = await _column_default_map(conn, "rsshub_sub")
        if all(
            _sqlite_default_is(defaults.get(column), "-100")
            for column in inherit_columns
        ):
            return

    await conn.exec_driver_sql(
        """
        CREATE TABLE rsshub_sub__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state INTEGER NOT NULL DEFAULT 1,
            user_id VARCHAR NOT NULL,
            feed_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '',
            target_session TEXT,
            platform_name TEXT,
            interval INTEGER NOT NULL DEFAULT -100,
            next_check_time DATETIME,
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
            display_media INTEGER NOT NULL DEFAULT -100,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES rsshub_user (id),
            FOREIGN KEY (feed_id) REFERENCES rsshub_feed (id)
        )
        """
    )
    await conn.exec_driver_sql(
        f"""
        INSERT INTO rsshub_sub__new (
            id, state, user_id, feed_id, title, tags, target_session, platform_name,
            interval, next_check_time, notify, send_mode, ai_prompt, length_limit,
            link_preview, display_author, display_via, display_title,
            display_entry_tags, style, display_media, created_at, updated_at
        )
        SELECT
            id,
            COALESCE({_select_expr(columns, "state", "1")}, 1),
            user_id,
            feed_id,
            COALESCE({_select_expr(columns, "title", "''")}, ''),
            COALESCE({_select_expr(columns, "tags", "''")}, ''),
            {_select_expr(columns, "target_session", "NULL")},
            {_select_expr(columns, "platform_name", "NULL")},
            {_legacy_sub_option_expr(columns, "interval", "10")},
            {_select_expr(columns, "next_check_time", "NULL")},
            {_legacy_sub_option_expr(columns, "notify", "1")},
            {_legacy_sub_option_expr(columns, "send_mode", "0")},
            COALESCE({_select_expr(columns, "ai_prompt", "''")}, ''),
            {_legacy_sub_option_expr(columns, "length_limit", "0")},
            {_legacy_sub_option_expr(columns, "link_preview", "0")},
            {_legacy_sub_option_expr(columns, "display_author", "0")},
            {_legacy_sub_option_expr(columns, "display_via", "0")},
            {_legacy_sub_option_expr(columns, "display_title", "0")},
            {_legacy_sub_option_expr(columns, "display_entry_tags", "-1")},
            {_legacy_sub_option_expr(columns, "style", "0")},
            {_legacy_sub_option_expr(columns, "display_media", "0")},
            COALESCE({_select_expr(columns, "created_at", "CURRENT_TIMESTAMP")}, CURRENT_TIMESTAMP),
            COALESCE({_select_expr(columns, "updated_at", "CURRENT_TIMESTAMP")}, CURRENT_TIMESTAMP)
        FROM rsshub_sub
        """
    )
    await conn.exec_driver_sql("DROP TABLE rsshub_sub")
    await conn.exec_driver_sql("ALTER TABLE rsshub_sub__new RENAME TO rsshub_sub")
    logger.info("迁移 V6: 重建 rsshub_sub，添加 ai_prompt 并移除旧配置/翻译字段")


async def upgrade(conn) -> None:
    await _rebuild_user_table(conn)
    await _rebuild_sub_table(conn)
