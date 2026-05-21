"""V10 add push history handler trace JSON."""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def _column_names(conn, table: str) -> set[str]:
    result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in result.fetchall()}


async def upgrade(conn) -> None:
    columns = await _column_names(conn, "rsshub_push_history")
    if "handler_trace" in columns:
        return
    await conn.exec_driver_sql(
        "ALTER TABLE rsshub_push_history ADD COLUMN handler_trace JSON"
    )
    logger.info("迁移 V10: 为 rsshub_push_history 添加 handler_trace")
