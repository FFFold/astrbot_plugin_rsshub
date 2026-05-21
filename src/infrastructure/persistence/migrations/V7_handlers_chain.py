"""V7 migrate ai_prompt fields to handlers JSON chain."""

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


async def _rebuild_user_table(conn) -> None:
    if not await _table_exists(conn, "rsshub_user"):
        return

    columns = await _column_names(conn, "rsshub_user")
    if "handlers" in columns and "ai_prompt" not in columns:
        return

    await conn.exec_driver_sql(
        """
        CREATE TABLE rsshub_user__new (
            id VARCHAR PRIMARY KEY,
            state INTEGER NOT NULL DEFAULT 1,
            interval INTEGER NOT NULL DEFAULT -100,
            notify INTEGER NOT NULL DEFAULT -100,
            send_mode INTEGER NOT NULL DEFAULT -100,
            handlers TEXT NOT NULL DEFAULT '[]',
            length_limit INTEGER NOT NULL DEFAULT -100,
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
        """
        INSERT INTO rsshub_user__new (
            id, state, interval, notify, send_mode, handlers, length_limit,
            display_author, display_via, display_title, display_entry_tags,
            style, display_media, default_target_session,
            needs_binding_notice, created_at, updated_at
        )
        SELECT
            id,
            COALESCE(state, 1),
            COALESCE(interval, -100),
            COALESCE(notify, -100),
            COALESCE(send_mode, -100),
            CASE
                WHEN TRIM(COALESCE(ai_prompt, '')) = '' THEN '[]'
                ELSE
                    '[{{"id":"builtin.ai_transform.default","type":"builtin","name":"ai_transform","status":1,"config":{{"prompt":'
                    || json_quote(TRIM(ai_prompt))
                    || '}}}}]'
            END,
            COALESCE(length_limit, -100),
            COALESCE(display_author, -100),
            COALESCE(display_via, -100),
            COALESCE(display_title, -100),
            COALESCE(display_entry_tags, -100),
            COALESCE(style, -100),
            COALESCE(display_media, -100),
            default_target_session,
            COALESCE(needs_binding_notice, 0),
            COALESCE(created_at, CURRENT_TIMESTAMP),
            COALESCE(updated_at, CURRENT_TIMESTAMP)
        FROM rsshub_user
        """
    )
    await conn.exec_driver_sql("DROP TABLE rsshub_user")
    await conn.exec_driver_sql("ALTER TABLE rsshub_user__new RENAME TO rsshub_user")
    logger.info("迁移 V7: 重建 rsshub_user，移除 ai_prompt 并迁移为 handlers")


async def _rebuild_sub_table(conn) -> None:
    if not await _table_exists(conn, "rsshub_sub"):
        return

    columns = await _column_names(conn, "rsshub_sub")
    if "handlers" in columns and "ai_prompt" not in columns:
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
            handlers TEXT NOT NULL DEFAULT '[]',
            length_limit INTEGER NOT NULL DEFAULT -100,
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
        """
        INSERT INTO rsshub_sub__new (
            id, state, user_id, feed_id, title, tags, target_session, platform_name,
            interval, next_check_time, notify, send_mode, handlers, length_limit,
            display_author, display_via, display_title, display_entry_tags,
            style, display_media, created_at, updated_at
        )
        SELECT
            id,
            COALESCE(state, 1),
            user_id,
            feed_id,
            COALESCE(title, ''),
            COALESCE(tags, ''),
            target_session,
            platform_name,
            COALESCE(interval, -100),
            next_check_time,
            COALESCE(notify, -100),
            COALESCE(send_mode, -100),
            CASE
                WHEN TRIM(COALESCE(ai_prompt, '')) = '' THEN '[]'
                ELSE
                    '[{{"id":"builtin.ai_transform.default","type":"builtin","name":"ai_transform","status":1,"config":{{"prompt":'
                    || json_quote(TRIM(ai_prompt))
                    || '}}}}]'
            END,
            COALESCE(length_limit, -100),
            COALESCE(display_author, -100),
            COALESCE(display_via, -100),
            COALESCE(display_title, -100),
            COALESCE(display_entry_tags, -100),
            COALESCE(style, -100),
            COALESCE(display_media, -100),
            COALESCE(created_at, CURRENT_TIMESTAMP),
            COALESCE(updated_at, CURRENT_TIMESTAMP)
        FROM rsshub_sub
        """
    )
    await conn.exec_driver_sql("DROP TABLE rsshub_sub")
    await conn.exec_driver_sql("ALTER TABLE rsshub_sub__new RENAME TO rsshub_sub")
    logger.info("迁移 V7: 重建 rsshub_sub，移除 ai_prompt 并迁移为 handlers")


async def upgrade(conn) -> None:
    await _rebuild_user_table(conn)
    await _rebuild_sub_table(conn)
