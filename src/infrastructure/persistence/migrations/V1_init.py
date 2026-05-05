"""V1 初始化迁移

创建基础数据库表结构：
- rsshub_user: 用户表
- rsshub_feed: Feed 表
- rsshub_sub: 订阅表
- rsshub_translation_cache: 翻译缓存表
- rsshub_push_history: 推送历史表
- rsshub_migration_record: 迁移记录表
"""

from __future__ import annotations

from ...utils import get_logger

logger = get_logger()


async def upgrade(conn) -> None:
    """执行 V1 初始化迁移"""

    async def _table_exists(table: str) -> bool:
        result = await conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return result.fetchone() is not None

    # 创建 rsshub_user 表
    if not await _table_exists("rsshub_user"):
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_user (
                id VARCHAR PRIMARY KEY,
                state INTEGER NOT NULL DEFAULT 0,
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
                translate INTEGER NOT NULL DEFAULT -100,
                translate_target_lang TEXT,
                default_target_session TEXT,
                needs_binding_notice INTEGER NOT NULL DEFAULT 0,
                use_user_config INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        logger.info("迁移 V1: 创建 rsshub_user 表")

    # 创建 rsshub_feed 表
    if not await _table_exists("rsshub_feed"):
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_feed (
                id INTEGER PRIMARY KEY,
                state INTEGER NOT NULL DEFAULT 1,
                link VARCHAR(4096) NOT NULL UNIQUE,
                title VARCHAR(1024) NOT NULL,
                entry_hashes JSON,
                etag VARCHAR(128),
                last_modified DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        logger.info("迁移 V1: 创建 rsshub_feed 表")

    # 创建 rsshub_sub 表
    if not await _table_exists("rsshub_sub"):
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
                translate INTEGER NOT NULL DEFAULT -100,
                translate_target_lang TEXT,
                use_sub_config INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES rsshub_user (id),
                FOREIGN KEY (feed_id) REFERENCES rsshub_feed (id)
            )
            """
        )
        logger.info("迁移 V1: 创建 rsshub_sub 表")

    # 创建 rsshub_translation_cache 表
    if not await _table_exists("rsshub_translation_cache"):
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_translation_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash VARCHAR(64) UNIQUE,
                provider VARCHAR(32),
                target_lang VARCHAR(16),
                translated_text TEXT NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        logger.info("迁移 V1: 创建 rsshub_translation_cache 表")

    # 创建 rsshub_push_history 表
    if not await _table_exists("rsshub_push_history"):
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_push_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sub_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                feed_id INTEGER NOT NULL,
                content VARCHAR NOT NULL DEFAULT '',
                media_urls JSON,
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
        logger.info("迁移 V1: 创建 rsshub_push_history 表")

    # 创建迁移记录表
    if not await _table_exists("rsshub_migration_record"):
        await conn.exec_driver_sql(
            """
            CREATE TABLE rsshub_migration_record (
                version VARCHAR(32) PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                description VARCHAR(256)
            )
            """
        )
        logger.info("迁移 V1: 创建 rsshub_migration_record 表")

    # 兼容性处理：将旧版迁移记录转换为新版整数版本
    result = await conn.exec_driver_sql(
        "SELECT version FROM rsshub_migration_record WHERE version LIKE 'v%'"
    )
    old_versions = [row[0] for row in result.fetchall()]
    if old_versions:
        logger.info("检测到旧版迁移记录: %s，转换为新版版本号", old_versions)
        # 旧版 v1.0.0 -> 新 V1, v1.1.0 -> V2, v1.1.1 -> V3, v2.0.0 -> V4
        mapping = {
            "v1.0.0": "1",
            "v1.1.0": "2",
            "v1.1.1": "3",
            "v2.0.0": "4",
        }
        for old_v in old_versions:
            new_v = mapping.get(old_v)
            if new_v:
                await conn.exec_driver_sql(
                    """
                    INSERT OR REPLACE INTO rsshub_migration_record (version, applied_at, description)
                    VALUES (?, datetime('now'), ?)
                    """,
                    (new_v, f"兼容旧版迁移: {old_v}"),
                )
                logger.info("已将 %s 映射为新版版本号 %s", old_v, new_v)

    logger.info("迁移 V1 完成: 初始化数据库表")
