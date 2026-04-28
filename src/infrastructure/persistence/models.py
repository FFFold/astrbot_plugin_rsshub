"""ORM 模型定义模块

定义数据库表结构对应的 SQLModel 模型。
所有模型继承自 RSSHubBaseModel，共享同一个 metadata。

注意:
    此模块仅包含 ORM 模型定义和数据结构，不包含业务逻辑方法。
    业务逻辑应放在领域层 (domain/entities/) 或仓库实现中。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, func
from sqlalchemy.orm import selectinload
from sqlmodel import Field, Relationship, SQLModel

from .database import RSSHubBaseModel

# ============================================================================
# 基础常量
# ============================================================================

INHERIT_VALUE = -100

EFFECTIVE_OPTION_KEYS = (
    "send_mode",
    "length_limit",
    "link_preview",
    "display_author",
    "display_via",
    "display_title",
    "display_entry_tags",
    "style",
    "display_media",
    "translate",
    "translate_target_lang",
)


# ============================================================================
# ORM 模型
# ============================================================================


class UserORM(RSSHubBaseModel, table=True):
    """用户 ORM 模型，映射 rsshub_user 表。"""

    __tablename__ = "rsshub_user"

    id: str = Field(default=None, primary_key=True, description="用户ID")
    state: int = Field(
        default=0, description="用户状态: -1=封禁, 0=访客, 1=用户, 100=管理员"
    )

    interval: int | None = Field(default=None, description="监控间隔(分钟)")
    notify: int = Field(default=1, description="是否通知: 0=禁用, 1=启用")
    send_mode: int = Field(
        default=0, description="发送模式: -1=仅链接, 0=自动, 1=Telegraph, 2=直接消息"
    )
    length_limit: int = Field(default=0, description="长度限制")
    link_preview: int = Field(default=0, description="链接预览: 0=自动, 1=强制启用")
    display_author: int = Field(
        default=0, description="显示作者: -1=禁用, 0=自动, 1=强制"
    )
    display_via: int = Field(
        default=0, description="显示来源: -2=完全禁用, -1=仅链接, 0=自动, 1=强制"
    )
    display_title: int = Field(
        default=0, description="显示标题: -1=禁用, 0=自动, 1=强制"
    )
    display_entry_tags: int = Field(default=-1, description="显示标签")
    style: int = Field(default=0, description="样式: 0=RSStT, 1=flowerss")
    display_media: int = Field(default=0, description="显示媒体: -1=禁用, 0=启用")
    translate: int = Field(
        default=INHERIT_VALUE, description="翻译: -100=继承, 0=禁用, 1=启用"
    )
    translate_target_lang: str | None = Field(
        default=None, max_length=16, description="翻译目标语言"
    )
    default_target_session: str | None = Field(
        default=None,
        max_length=255,
        description="默认推送目标会话(unified_msg_origin)",
    )
    needs_binding_notice: int = Field(default=0, description="是否需要提示绑定推送目标")
    use_user_config: bool = Field(
        default=False,
        description="是否使用用户自身配置",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
        description="更新时间",
    )

    subs: list["SubORM"] = Relationship(back_populates="user")


class FeedORM(RSSHubBaseModel, table=True):
    """Feed ORM 模型，映射 rsshub_feed 表。"""

    __tablename__ = "rsshub_feed"

    id: int | None = Field(default=None, primary_key=True)
    state: int = Field(default=1, description="Feed状态: 0=停用, 1=启用")
    link: str = Field(max_length=4096, unique=True, description="Feed链接")
    title: str = Field(max_length=1024, description="Feed标题")
    entry_hashes: list[Any] | None = Field(
        default=None, sa_column=Column(JSON), description="条目哈希历史"
    )
    etag: str | None = Field(default=None, max_length=128, description="ETag")
    last_modified: datetime | None = Field(default=None, description="最后修改时间")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
        description="更新时间",
    )

    subs: list["SubORM"] = Relationship(back_populates="feed")


class SubORM(RSSHubBaseModel, table=True):
    """订阅 ORM 模型，映射 rsshub_sub 表。"""

    __tablename__ = "rsshub_sub"

    id: int | None = Field(default=None, primary_key=True)
    state: int = Field(default=1, description="订阅状态: 0=停用, 1=启用")

    user_id: str = Field(foreign_key="rsshub_user.id", description="用户ID")
    feed_id: int = Field(foreign_key="rsshub_feed.id", description="FeedID")

    title: str = Field(default="", max_length=1024, description="订阅标题")
    tags: str = Field(default="", max_length=255, description="标签")
    target_session: str | None = Field(
        default=None,
        max_length=255,
        description="订阅推送目标会话",
    )
    platform_name: str | None = Field(
        default=None,
        max_length=64,
        description="平台类型名",
    )

    interval: int | None = Field(default=None, description="监控间隔(分钟)")
    next_check_time: datetime | None = Field(default=None, description="下次检查时间")
    notify: int = Field(default=INHERIT_VALUE, description="是否通知")
    send_mode: int = Field(default=INHERIT_VALUE, description="发送模式")
    length_limit: int = Field(default=INHERIT_VALUE, description="长度限制")
    link_preview: int = Field(default=INHERIT_VALUE, description="链接预览")
    display_author: int = Field(default=INHERIT_VALUE, description="显示作者")
    display_via: int = Field(default=INHERIT_VALUE, description="显示来源")
    display_title: int = Field(default=INHERIT_VALUE, description="显示标题")
    display_entry_tags: int = Field(default=INHERIT_VALUE, description="显示标签")
    style: int = Field(default=INHERIT_VALUE, description="样式")
    display_media: int = Field(default=INHERIT_VALUE, description="显示媒体")
    translate: int = Field(default=INHERIT_VALUE, description="翻译")
    translate_target_lang: str | None = Field(
        default=None, max_length=16, description="翻译目标语言"
    )
    use_sub_config: bool = Field(
        default=False,
        description="是否使用订阅自身配置",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
        description="更新时间",
    )

    user: "UserORM" = Relationship(back_populates="subs")
    feed: "FeedORM" = Relationship(back_populates="subs")


class TranslationCacheORM(RSSHubBaseModel, table=True):
    """翻译缓存 ORM 模型，映射 rsshub_translation_cache 表。"""

    __tablename__ = "rsshub_translation_cache"

    id: int | None = Field(default=None, primary_key=True)
    hash: str = Field(max_length=64, unique=True, index=True, description="原文哈希")
    provider: str = Field(max_length=32, description="翻译器类型")
    target_lang: str = Field(max_length=16, description="目标语言")
    translated_text: str = Field(default="", description="翻译后的文本")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )


class PushHistoryORM(RSSHubBaseModel, table=True):
    """推送历史 ORM 模型，映射 rsshub_push_history 表。"""

    __tablename__ = "rsshub_push_history"

    id: int | None = Field(default=None, primary_key=True)
    sub_id: int = Field(foreign_key="rsshub_sub.id", description="订阅ID")
    user_id: str = Field(foreign_key="rsshub_user.id", description="用户ID")
    feed_id: int = Field(foreign_key="rsshub_feed.id", description="FeedID")

    content: str = Field(default="", description="格式化后的消息内容")
    media_urls: list[str] | None = Field(
        default=None, sa_column=Column(JSON), description="媒体URL列表"
    )

    entry_title: str = Field(default="", max_length=1024, description="条目标题")
    entry_link: str = Field(default="", max_length=4096, description="条目链接")
    entry_guid: str | None = Field(default=None, max_length=512, description="条目GUID")

    feed_title: str = Field(default="", max_length=1024, description="Feed标题")
    feed_link: str = Field(default="", max_length=4096, description="Feed链接")

    platform_name: str | None = Field(
        default=None, max_length=64, description="平台名称"
    )
    target_session: str | None = Field(
        default=None, max_length=255, description="目标会话"
    )

    status: str | None = Field(
        default=None, max_length=16, description="状态: pending/success/failed"
    )
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    fail_reason: str | None = Field(
        default=None, max_length=512, description="失败原因"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
        description="更新时间",
    )
    completed_at: datetime | None = Field(default=None, description="完成时间")


class MigrationRecordORM(RSSHubBaseModel, table=True):
    """迁移记录 ORM 模型，映射 rsshub_migration_record 表。"""

    __tablename__ = "rsshub_migration_record"

    version: str = Field(primary_key=True, max_length=32, description="迁移版本号")
    applied_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="应用时间",
    )
    description: str = Field(default="", max_length=256, description="迁移描述")
