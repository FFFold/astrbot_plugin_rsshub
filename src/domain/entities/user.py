"""
用户领域实体

代表系统中的一个用户，包含用户状态、默认订阅选项和推送配置。
不包含任何 ORM 或持久化逻辑。
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..constants import INHERIT_VALUE


class User(BaseModel):
    """
    用户领域实体

    代表系统中的一个用户，包含用户状态、默认订阅选项和推送配置。
    """

    id: str
    """用户ID（主键）"""

    state: int = Field(
        default=0, description="用户状态: -1=封禁, 0=访客, 1=用户, 100=管理员"
    )

    interval: int | None = Field(default=None, description="监控间隔（分钟）")
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
        default=None, max_length=255, description="默认推送目标会话(unified_msg_origin)"
    )
    needs_binding_notice: int = Field(default=0, description="是否需要提示绑定推送目标")
    use_user_config: bool = Field(
        default=False,
        description="是否使用用户自身配置: true=使用User表, false=继承全局配置",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="更新时间"
    )

    def is_active(self) -> bool:
        """检查用户是否处于启用状态（非封禁）"""
        return self.state >= 0

    def is_admin(self) -> bool:
        """检查用户是否为管理员"""
        return self.state >= 100

    def activate(self) -> "User":
        """将用户状态设为启用"""
        self.state = 1
        self.updated_at = datetime.now(timezone.utc)
        return self

    def deactivate(self) -> "User":
        """将用户状态设为停用"""
        self.state = 0
        self.updated_at = datetime.now(timezone.utc)
        return self

    def set_default_target(self, target_session: str) -> "User":
        """设置默认推送目标会话"""
        self.default_target_session = target_session
        self.needs_binding_notice = 0
        self.updated_at = datetime.now(timezone.utc)
        return self

    def mark_binding_notice(self) -> "User":
        """标记需要绑定通知"""
        self.needs_binding_notice = 1
        self.updated_at = datetime.now(timezone.utc)
        return self

    def consume_binding_notice(self) -> bool:
        """消费绑定通知标记"""
        if self.needs_binding_notice == 0:
            return False
        self.needs_binding_notice = 0
        self.updated_at = datetime.now(timezone.utc)
        return True

    def get_effective_option(self, key: str) -> int | str | None:
        """
        获取生效的配置选项值

        Args:
            key: 选项名称

        Returns:
            选项值，如果未设置则返回None
        """
        if hasattr(self, key):
            value = getattr(self, key)
            if value != INHERIT_VALUE:
                return value
        return None
