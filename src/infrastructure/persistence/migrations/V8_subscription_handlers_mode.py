"""V8 add handlers_mode for subscription handler inheritance semantics."""

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


async def _normalize_existing_rows(conn) -> None:
    await conn.exec_driver_sql(
        """
        UPDATE rsshub_sub
        SET handlers_mode = CASE
            WHEN handlers IS NULL THEN 'inherit'
            WHEN json_valid(handlers) AND json_array_length(handlers) = 0 THEN 'inherit'
            WHEN NOT json_valid(handlers) AND REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(TRIM(COALESCE(handlers, '[]')), ' ', ''),
                        CHAR(10),
                        ''
                    ),
                    CHAR(13),
                    ''
                ),
                CHAR(9),
                ''
            ) IN ('', '[]') THEN 'inherit'
            ELSE 'override'
        END
        """
    )


async def _rebuild_sub_table(conn) -> None:
    if not await _table_exists(conn, "rsshub_sub"):
        return

    columns = await _column_names(conn, "rsshub_sub")
    if "handlers_mode" in columns:
        await _normalize_existing_rows(conn)
        return

    await conn.exec_driver_sql(
        "ALTER TABLE rsshub_sub ADD COLUMN handlers_mode TEXT NOT NULL DEFAULT 'inherit'"
    )
    await _normalize_existing_rows(conn)
    logger.info("迁移 V8: 为 rsshub_sub 添加 handlers_mode")


async def upgrade(conn) -> None:
    await _rebuild_sub_table(conn)
