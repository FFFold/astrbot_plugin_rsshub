"""翻译缓存仓库实现

基于 SQLModel/SQLAlchemy 实现 TranslationCacheRepository 接口。
负责翻译缓存实体的持久化操作。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func
from sqlmodel import select

from ...domain.entities.translation_cache import TranslationCache
from ...domain.repositories.translation_cache_repository import (
    TranslationCacheRepository,
)
from ..utils import get_logger
from .database import get_database
from .models import TranslationCacheORM

logger = get_logger()


class TranslationCacheRepositoryImpl:
    """翻译缓存仓库实现类"""

    async def get_by_id(self, cache_id: int) -> TranslationCache | None:
        """根据ID获取翻译缓存"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(TranslationCacheORM, cache_id)
            return self._to_entity(orm) if orm else None

    async def get_by_hash(self, hash: str) -> TranslationCache | None:
        """根据哈希获取翻译缓存"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(TranslationCacheORM).where(TranslationCacheORM.hash == hash)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[TranslationCache]:
        """获取所有翻译缓存"""
        db = get_database()
        async with db.get_session() as session:
            stmt = (
                select(TranslationCacheORM)
                .order_by(TranslationCacheORM.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def delete(self, cache_id: int) -> bool:
        """删除翻译缓存"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(TranslationCacheORM, cache_id)
            if not orm:
                return False
            await session.delete(orm)
            await session.commit()
            return True

    async def delete_old_records(self, days: int = 30) -> int:
        """删除指定天数前的翻译缓存"""
        db = get_database()
        async with db.get_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = (
                delete(TranslationCacheORM)
                .where(TranslationCacheORM.created_at < cutoff_date)
                .execution_options(synchronize_session=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def get_stats(self) -> dict[str, int]:
        """获取翻译缓存统计信息"""
        db = get_database()
        async with db.get_session() as session:
            total_stmt = select(func.count()).select_from(TranslationCacheORM)
            total = (await session.execute(total_stmt)).scalar_one() or 0

            return {
                "total": int(total),
            }

    @staticmethod
    def _to_entity(orm: TranslationCacheORM) -> TranslationCache:
        """将 ORM 模型转换为领域实体"""
        return TranslationCache(
            id=orm.id,
            hash=orm.hash,
            provider=orm.provider,
            target_lang=orm.target_lang,
            translated_text=orm.translated_text,
            created_at=orm.created_at,
        )

    @staticmethod
    def _to_orm(cache: TranslationCache) -> TranslationCacheORM:
        """将领域实体转换为 ORM 模型"""
        return TranslationCacheORM(
            id=cache.id,
            hash=cache.hash,
            provider=cache.provider,
            target_lang=cache.target_lang,
            translated_text=cache.translated_text,
            created_at=cache.created_at,
        )


_translation_cache_repo_instance: TranslationCacheRepositoryImpl | None = None


def get_translation_cache_repository() -> TranslationCacheRepository:
    """获取翻译缓存仓库实例"""
    global _translation_cache_repo_instance
    if _translation_cache_repo_instance is None:
        _translation_cache_repo_instance = TranslationCacheRepositoryImpl()
    return _translation_cache_repo_instance
