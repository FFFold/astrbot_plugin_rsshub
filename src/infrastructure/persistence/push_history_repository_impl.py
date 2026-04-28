"""推送历史仓库实现

基于 SQLModel/SQLAlchemy 实现 PushHistoryRepository 接口。
负责推送历史实体的持久化操作。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func
from sqlmodel import select

from ...domain.entities.push_history import PushHistory
from ...domain.repositories.push_history_repository import PushHistoryRepository
from ..utils import get_logger
from .database import get_database
from .models import PushHistoryORM

logger = get_logger()


class PushHistoryRepositoryImpl:
    """推送历史仓库实现类"""

    async def get_by_id(self, history_id: int) -> PushHistory | None:
        """根据ID获取推送历史"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(PushHistoryORM, history_id)
            return self._to_entity(orm) if orm else None

    async def get_by_sub(
        self, sub_id: int, limit: int | None = None, status: str | None = None
    ) -> list[PushHistory]:
        """获取订阅的推送历史"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(PushHistoryORM).where(PushHistoryORM.sub_id == sub_id)
            if status:
                stmt = stmt.where(PushHistoryORM.status == status)
            stmt = stmt.order_by(PushHistoryORM.created_at.desc())
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def get_pending_for_retry(self, limit: int = 100) -> list[PushHistory]:
        """获取需要重试的推送记录"""
        db = get_database()
        async with db.get_session() as session:
            stmt = (
                select(PushHistoryORM)
                .where(
                    PushHistoryORM.status == "failed",
                    PushHistoryORM.retry_count < PushHistoryORM.max_retries,
                )
                .order_by(PushHistoryORM.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def save(self, history: PushHistory) -> PushHistory:
        """保存推送历史"""
        db = get_database()
        async with db.get_session() as session:
            orm = self._to_orm(history)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def delete_old_records(self, days: int = 30) -> int:
        """删除指定天数前的历史记录"""
        db = get_database()
        async with db.get_session() as session:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            stmt = (
                delete(PushHistoryORM)
                .where(PushHistoryORM.created_at < cutoff_date)
                .execution_options(synchronize_session=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def get_stats(self) -> dict[str, int]:
        """获取推送统计信息"""
        db = get_database()
        async with db.get_session() as session:
            total_stmt = select(func.count()).select_from(PushHistoryORM)
            total = (await session.execute(total_stmt)).scalar_one() or 0

            status_counts = {}
            for status in ["pending", "success", "failed"]:
                stmt = (
                    select(func.count())
                    .select_from(PushHistoryORM)
                    .where(PushHistoryORM.status == status)
                )
                count = (await session.execute(stmt)).scalar_one() or 0
                status_counts[status] = int(count)

            return {
                "total": int(total),
                **status_counts,
            }

    @staticmethod
    def _to_entity(orm: PushHistoryORM) -> PushHistory:
        """将 ORM 模型转换为领域实体"""
        return PushHistory(
            id=orm.id,
            sub_id=orm.sub_id,
            user_id=orm.user_id,
            feed_id=orm.feed_id,
            content=orm.content,
            media_urls=orm.media_urls,
            entry_title=orm.entry_title,
            entry_link=orm.entry_link,
            entry_guid=orm.entry_guid,
            feed_title=orm.feed_title,
            feed_link=orm.feed_link,
            platform_name=orm.platform_name,
            target_session=orm.target_session,
            status=orm.status,
            retry_count=orm.retry_count,
            max_retries=orm.max_retries,
            fail_reason=orm.fail_reason,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
        )

    @staticmethod
    def _to_orm(history: PushHistory) -> PushHistoryORM:
        """将领域实体转换为 ORM 模型"""
        return PushHistoryORM(
            id=history.id,
            sub_id=history.sub_id,
            user_id=history.user_id,
            feed_id=history.feed_id,
            content=history.content,
            media_urls=history.media_urls,
            entry_title=history.entry_title,
            entry_link=history.entry_link,
            entry_guid=history.entry_guid,
            feed_title=history.feed_title,
            feed_link=history.feed_link,
            platform_name=history.platform_name,
            target_session=history.target_session,
            status=history.status,
            retry_count=history.retry_count,
            max_retries=history.max_retries,
            fail_reason=history.fail_reason,
            created_at=history.created_at,
            updated_at=history.updated_at,
            completed_at=history.completed_at,
        )


_history_repo_instance: PushHistoryRepositoryImpl | None = None


def get_push_history_repository() -> PushHistoryRepository:
    """获取推送历史仓库实例"""
    global _history_repo_instance
    if _history_repo_instance is None:
        _history_repo_instance = PushHistoryRepositoryImpl()
    return _history_repo_instance
