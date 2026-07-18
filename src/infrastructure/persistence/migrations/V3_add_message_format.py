"""V3 迁移：在 rsshub_user 和 rsshub_sub 表中添加 message_format 列"""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def upgrade(conn) -> None:
    """执行 V3 迁移：添加 message_format 列"""

    async def _table_exists(table: str) -> bool:
        result = await conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return result.fetchone() is not None

    async def _column_exists(table: str, column: str) -> bool:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
        return any(str(row[1]) == column for row in result.fetchall())

    for table in ["rsshub_user", "rsshub_sub"]:
        if not await _table_exists(table):
            logger.info("迁移 V3: %s 表不存在，跳过", table)
            continue

        if await _column_exists(table, "message_format"):
            logger.info("迁移 V3: %s.message_format 列已存在，跳过", table)
            continue

        try:
            await conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN message_format INTEGER DEFAULT -100 NOT NULL"
            )
            logger.info("迁移 V3: 成功添加 %s.message_format 列", table)
        except Exception as e:
            logger.error("迁移 V3: 添加 %s.message_format 列失败: %s", table, e)
            raise

    logger.info("迁移 V3 完成: 添加 message_format 字段")
