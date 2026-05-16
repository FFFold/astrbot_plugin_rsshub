"""设置用户设置命令

处理设置用户默认配置的业务用例。
"""

from __future__ import annotations

from ...domain.repositories.user_repository import UserRepository
from ..dto.result_dto import CommandResult

# 设置选项的合法值范围
VALID_SETTINGS = {
    "interval": (1, 60),  # 分钟
    "notify": (0, 1),
    "send_mode": (-1, 2),  # -1=仅链接, 0=自动, 1=Telegraph, 2=直接消息
    "length_limit": (0, 10000),
    "link_preview": (0, 1),
    "display_author": (-1, 1),
    "display_via": (-2, 1),
    "display_title": (-1, 1),
    "display_entry_tags": (-1, 1),
    "style": (0, 1),
    "display_media": (-1, 1),
    "translate": (-100, 1),  # -100=继承, 0=禁用, 1=启用
}


class SetUserSettingsCommand:
    """设置用户设置命令

    处理设置用户默认配置的业务用例。
    """

    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(
        self,
        user_id: str,
        key: str,
        value: str,
    ) -> CommandResult:
        """执行设置用户设置命令

        Args:
            user_id: 用户 ID
            key: 设置项名称
            value: 设置值

        Returns:
            CommandResult: 命令执行结果
        """
        # 获取或创建用户
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            # 创建新用户
            from ...domain.entities.user import User

            user = User(id=user_id)

        option_key = key.strip().lower()
        parsed_value: int | str

        # 解析值
        if option_key in {"title", "tags", "translate_target_lang"}:
            parsed_value = str(value).strip()
        else:
            try:
                parsed_value = int(value)
            except ValueError:
                return CommandResult(
                    success=False,
                    message=f"选项 {option_key} 需要数字值",
                )

            # 验证范围
            if option_key in VALID_SETTINGS:
                min_val, max_val = VALID_SETTINGS[option_key]
                if not min_val <= parsed_value <= max_val:
                    return CommandResult(
                        success=False,
                        message=f"{option_key} 的值 {parsed_value} 超出范围 [{min_val}, {max_val}]",
                    )

        # 获取旧值用于显示
        old_value = getattr(user, option_key, None)

        # 应用设置
        setattr(user, option_key, parsed_value)

        # 保存用户
        await self._user_repo.save(user)

        # 格式化显示值
        def fmt(val):
            if val is None:
                return "未设置"
            if isinstance(val, bool) or val in (0, 1, -100, -1, -2):
                val_map = {0: "禁用", 1: "启用", -100: "继承", -1: "禁用", -2: "不显示"}
                return val_map.get(val, str(val))
            return str(val)

        return CommandResult(
            success=True,
            message=f"用户配置已更新:\n{option_key}: {fmt(old_value)} → {fmt(parsed_value)}",
        )
