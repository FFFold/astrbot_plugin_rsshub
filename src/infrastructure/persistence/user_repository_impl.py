"""用户仓库实现

基于 SQLModel/SQLAlchemy 实现 UserRepository 接口。
负责用户实体的持久化操作。
"""

from __future__ import annotations

from sqlmodel import select

from ...domain.entities.user import User
from ...domain.repositories.user_repository import UserRepository
from ..utils import get_logger
from .database import get_database
from .models import UserORM

logger = get_logger()


class UserRepositoryImpl:
    """用户仓库实现类"""

    async def get_by_id(self, user_id: str) -> User | None:
        """根据ID获取用户"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(UserORM, user_id)
            return self._to_entity(orm) if orm else None

    async def get_or_create(self, user_id: str) -> User:
        """获取或创建用户"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(UserORM, user_id)
            if not orm:
                orm = UserORM(id=user_id)
                session.add(orm)
                await session.commit()
                await session.refresh(orm)
                logger.info("创建新用户: %s", user_id)
            return self._to_entity(orm)

    async def save(self, user: User) -> User:
        """保存用户"""
        db = get_database()
        async with db.get_session() as session:
            orm = self._to_orm(user)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def update_defaults(self, user_id: str, **kwargs) -> User | None:
        """更新用户默认配置"""
        db = get_database()
        async with db.get_session() as session:
            orm = await session.get(UserORM, user_id)
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
    def _to_entity(orm: UserORM) -> User:
        """将 ORM 模型转换为领域实体"""
        return User(
            id=orm.id,
            state=orm.state,
            interval=orm.interval,
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
            default_target_session=orm.default_target_session,
            needs_binding_notice=orm.needs_binding_notice,
            use_user_config=orm.use_user_config,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _to_orm(user: User) -> UserORM:
        """将领域实体转换为 ORM 模型"""
        return UserORM(
            id=user.id,
            state=user.state,
            interval=user.interval,
            notify=user.notify,
            send_mode=user.send_mode,
            length_limit=user.length_limit,
            link_preview=user.link_preview,
            display_author=user.display_author,
            display_via=user.display_via,
            display_title=user.display_title,
            display_entry_tags=user.display_entry_tags,
            style=user.style,
            display_media=user.display_media,
            translate=user.translate,
            translate_target_lang=user.translate_target_lang,
            default_target_session=user.default_target_session,
            needs_binding_notice=user.needs_binding_notice,
            use_user_config=user.use_user_config,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


# 提供 get 方法获取单例
_user_repo_instance: UserRepositoryImpl | None = None


def get_user_repository() -> UserRepository:
    """获取用户仓库实例"""
    global _user_repo_instance
    if _user_repo_instance is None:
        _user_repo_instance = UserRepositoryImpl()
    return _user_repo_instance
