"""订阅仓库实现

基于 SQLModel/SQLAlchemy 实现 SubscriptionRepository 接口。
负责订阅实体的持久化操作。
"""

from __future__ import annotations

from sqlmodel import asc, select

from .database import get_database
from .models import SubORM
from ..utils import get_logger
from ...domain.entities.subscription import Subscription

logger = get_logger()


class SubscriptionRepositoryImpl:
    """订阅仓库实现类"""

    async def get_by_id(self, sub_id: int) -> Subscription | None:
        """根据ID获取订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(SubORM).where(SubORM.id == sub_id)
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def get_by_user(self, user_id: str) -> list[Subscription]:
        """获取用户的所有订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = (
                select(SubORM).where(SubORM.user_id == user_id).order_by(asc(SubORM.id))
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def get_by_user_and_feed(
        self, user_id: str, feed_id: int
    ) -> Subscription | None:
        """根据用户和Feed获取订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(SubORM).where(
                SubORM.user_id == user_id,
                SubORM.feed_id == feed_id,
            )
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def get_all_active(self) -> list[Subscription]:
        """获取所有启用的订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(SubORM).where(SubORM.state == 1).order_by(asc(SubORM.id))
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def get_active_by_feed_id(self, feed_id: int) -> list[Subscription]:
        """获取指定Feed的所有启用订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = (
                select(SubORM)
                .where(SubORM.feed_id == feed_id, SubORM.state == 1)
                .order_by(asc(SubORM.id))
            )
            result = await session.execute(stmt)
            orms = result.scalars().all()
            return [self._to_entity(orm) for orm in orms]

    async def save(self, subscription: Subscription) -> Subscription:
        """保存订阅"""
        db = get_database()
        async with db.get_session() as session:
            orm = self._to_orm(subscription)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def delete(self, subscription: Subscription) -> None:
        """删除订阅"""
        db = get_database()
        async with db.get_session() as session:
            if subscription.id is None:
                return
            db_sub = await session.get(SubORM, subscription.id)
            if db_sub:
                await session.delete(db_sub)
                await session.commit()

    async def delete_all_by_user(self, user_id: str) -> int:
        """删除用户的所有订阅"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(SubORM).where(SubORM.user_id == user_id)
            result = await session.execute(stmt)
            subs = list(result.scalars().all())
            count = len(subs)
            for sub in subs:
                await session.delete(sub)
            if count > 0:
                await session.commit()
            return count

    async def update_options(
        self, sub_id: int, user_id: str, **kwargs
    ) -> Subscription | None:
        """更新订阅配置选项"""
        db = get_database()
        async with db.get_session() as session:
            stmt = select(SubORM).where(
                SubORM.id == sub_id,
                SubORM.user_id == user_id,
            )
            result = await session.execute(stmt)
            orm = result.scalar_one_or_none()
            if not orm:
                return None
            for key, value in kwargs.items():
                if hasattr(orm, key):
                    setattr(orm, key, value)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    @staticmethod
    def _to_entity(orm: SubORM) -> Subscription:
        """将 ORM 模型转换为领域实体"""
        return Subscription(
            id=orm.id,
            state=orm.state,
            user_id=orm.user_id,
            feed_id=orm.feed_id,
            title=orm.title,
            tags=orm.tags,
            target_session=orm.target_session,
            platform_name=orm.platform_name,
            interval=orm.interval,
            next_check_time=orm.next_check_time,
            notify=orm.notify,
            send_mode=orm.send_mode,
            length_limit=orm.length_limit,
            link_preview=orm.link_preview,
            display_author=orm.display_author,
            display_via=orm.display_via,
            display_title=orm.display_title,
            display_entry_tags=orm.display_entry_tags,
            style=orm.style,
            display_media=orm.display_media,
            translate=orm.translate,
            translate_target_lang=orm.translate_target_lang,
            use_sub_config=orm.use_sub_config,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _to_orm(sub: Subscription) -> SubORM:
        """将领域实体转换为 ORM 模型"""
        return SubORM(
            id=sub.id,
            state=sub.state,
            user_id=sub.user_id,
            feed_id=sub.feed_id,
            title=sub.title,
            tags=sub.tags,
            target_session=sub.target_session,
            platform_name=sub.platform_name,
            interval=sub.interval,
            next_check_time=sub.next_check_time,
            notify=sub.notify,
            send_mode=sub.send_mode,
            length_limit=sub.length_limit,
            link_preview=sub.link_preview,
            display_author=sub.display_author,
            display_via=sub.display_via,
            display_title=sub.display_title,
            display_entry_tags=sub.display_entry_tags,
            style=sub.style,
            display_media=sub.display_media,
            translate=sub.translate,
            translate_target_lang=sub.translate_target_lang,
            use_sub_config=sub.use_sub_config,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
        )


_sub_repo_instance: SubscriptionRepositoryImpl | None = None


def get_subscription_repository() -> SubscriptionRepositoryImpl:
    """获取订阅仓库实例"""
    global _sub_repo_instance
    if _sub_repo_instance is None:
        _sub_repo_instance = SubscriptionRepositoryImpl()
    return _sub_repo_instance
