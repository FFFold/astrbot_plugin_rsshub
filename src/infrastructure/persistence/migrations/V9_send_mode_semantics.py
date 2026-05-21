"""V9 normalize legacy send_mode semantics to link/auto/direct."""

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


async def _normalize_table(conn, table: str) -> bool:
    if not await _table_exists(conn, table):
        return False

    columns = await _column_names(conn, table)
    if "send_mode" not in columns:
        return False

    result = await conn.exec_driver_sql(
        f"""
        UPDATE {table}
        SET send_mode = CASE
            WHEN send_mode = 2 THEN 1
            WHEN send_mode = 1 THEN 0
            ELSE send_mode
        END
        WHERE send_mode IN (1, 2)
        """
    )
    updated = int(getattr(result, "rowcount", 0) or 0)
    if updated > 0:
        logger.info("迁移 V9: 规范化 %s 的 send_mode 语义，更新 %s 行", table, updated)
    return updated > 0


async def upgrade(conn) -> None:
    await _normalize_table(conn, "rsshub_user")
    await _normalize_table(conn, "rsshub_sub")
