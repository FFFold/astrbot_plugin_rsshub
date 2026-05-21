"""V5 push history compatibility for agent-originated pushes."""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def _column_names(conn, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in result.fetchall()}


async def _index_exists(conn, index_name: str) -> bool:
    result = await conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return result.fetchone() is not None


async def _rebuild_push_history_table(conn) -> None:
    columns = await _column_names(conn, "rsshub_push_history")
    handler_trace_expr = "handler_trace" if "handler_trace" in columns else "NULL"
    await conn.exec_driver_sql(
        "DROP INDEX IF EXISTS idx_rsshub_push_history_scope_guid"
    )
    await conn.exec_driver_sql(
        """
        CREATE TABLE rsshub_push_history__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_id INTEGER,
            user_id VARCHAR NOT NULL,
            feed_id INTEGER,
            source_type VARCHAR(16) NOT NULL DEFAULT 'feed',
            source_key VARCHAR(255),
            content VARCHAR NOT NULL DEFAULT '',
            raw_xml TEXT,
            media_urls JSON,
            handler_trace JSON,
            entry_title VARCHAR(1024) NOT NULL DEFAULT '',
            entry_link VARCHAR(4096) NOT NULL DEFAULT '',
            entry_guid VARCHAR(512),
            feed_title VARCHAR(1024) NOT NULL DEFAULT '',
            feed_link VARCHAR(4096) NOT NULL DEFAULT '',
            platform_name VARCHAR(64),
            target_session VARCHAR(255),
            status VARCHAR(16),
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            fail_reason VARCHAR(512),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (sub_id) REFERENCES rsshub_sub (id),
            FOREIGN KEY (user_id) REFERENCES rsshub_user (id),
            FOREIGN KEY (feed_id) REFERENCES rsshub_feed (id)
        )
        """
    )
    await conn.exec_driver_sql(
        f"""
        INSERT INTO rsshub_push_history__new (
            id, sub_id, user_id, feed_id, source_type, source_key, content, raw_xml, media_urls, handler_trace,
            entry_title, entry_link, entry_guid, feed_title, feed_link,
            platform_name, target_session, status, retry_count, max_retries,
            fail_reason, created_at, updated_at, completed_at
        )
        SELECT
            id,
            sub_id,
            user_id,
            feed_id,
            COALESCE(source_type, 'feed'),
            source_key,
            content,
            raw_xml,
            media_urls,
            {handler_trace_expr},
            entry_title,
            entry_link,
            entry_guid,
            feed_title,
            feed_link,
            platform_name,
            target_session,
            status,
            retry_count,
            max_retries,
            fail_reason,
            created_at,
            updated_at,
            completed_at
        FROM rsshub_push_history
        """
    )
    await conn.exec_driver_sql("DROP TABLE rsshub_push_history")
    await conn.exec_driver_sql(
        "ALTER TABLE rsshub_push_history__new RENAME TO rsshub_push_history"
    )
    await conn.exec_driver_sql(
        """
        CREATE INDEX idx_rsshub_push_history_scope_guid
        ON rsshub_push_history (source_type, user_id, target_session, source_key, entry_guid, status)
        """
    )


async def upgrade(conn) -> None:
    columns = await _column_names(conn, "rsshub_push_history")

    if "source_type" not in columns:
        await conn.exec_driver_sql(
            "ALTER TABLE rsshub_push_history ADD COLUMN source_type VARCHAR(16) NOT NULL DEFAULT 'feed'"
        )
        logger.info("迁移 V5: 为 rsshub_push_history 添加 source_type")

    if "source_key" not in columns:
        await conn.exec_driver_sql(
            "ALTER TABLE rsshub_push_history ADD COLUMN source_key VARCHAR(255)"
        )
        logger.info("迁移 V5: 为 rsshub_push_history 添加 source_key")

    if "raw_xml" not in columns:
        await conn.exec_driver_sql(
            "ALTER TABLE rsshub_push_history ADD COLUMN raw_xml TEXT"
        )
        logger.info("迁移 V5: 为 rsshub_push_history 添加 raw_xml")

    if "handler_trace" not in columns:
        await conn.exec_driver_sql(
            "ALTER TABLE rsshub_push_history ADD COLUMN handler_trace JSON"
        )
        logger.info("迁移 V5: 为 rsshub_push_history 添加 handler_trace")

    sub_info = await conn.exec_driver_sql("PRAGMA table_info(rsshub_push_history)")
    nullable = {
        str(row[1]): int(row[3]) == 0  # notnull == 0
        for row in sub_info.fetchall()
    }
    if not nullable.get("sub_id", True) or not nullable.get("feed_id", True):
        await _rebuild_push_history_table(conn)
        logger.info(
            "迁移 V5: 重建 rsshub_push_history 以允许 agent 记录空 sub_id/feed_id"
        )
    elif not await _index_exists(conn, "idx_rsshub_push_history_scope_guid"):
        await conn.exec_driver_sql(
            """
            CREATE INDEX idx_rsshub_push_history_scope_guid
            ON rsshub_push_history (source_type, user_id, target_session, source_key, entry_guid, status)
            """
        )
        logger.info("迁移 V5: 创建 rsshub_push_history 作用域去重索引")
