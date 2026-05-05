"""设置用户设置命令

处理设置用户默认配置的业务用例。
"""

from __future__ import annotations

from ...domain.entities.user import User
from ...domain.repositories.user_repository import UserRepository
from ..dto.result_dto import CommandResult
from ..dto.user_dto import UserDTO

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
        settings: dict[str, int | str],
    ) -> CommandResult:
        """执行设置用户设置命令

        Args:
            user_id: 用户 ID
            settings: 设置项字典

        Returns:
            CommandResult: 命令执行结果
        """
        # 获取或创建用户
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            user = User(id=user_id)

        # 验证并应用设置
        errors = []
        applied = []

        for key, value in settings.items():
            # 跳过未知设置项
            if not hasattr(user, key):
                errors.append(f"未知设置项: {key}")
                continue

            # 验证整数值范围
            if key in VALID_SETTINGS:
                min_val, max_val = VALID_SETTINGS[key]
                try:
                    int_value = int(value)
                    if not min_val <= int_value <= max_val:
                        errors.append(
                            f"{key} 的值 {int_value} 超出范围 [{min_val}, {max_val}]"
                        )
                        continue
                    setattr(user, key, int_value)
                    applied.append(f"{key}={int_value}")
                except (ValueError, TypeError):
                    errors.append(f"{key} 必须是整数")
                    continue
            else:
                # 字符串类型设置
                setattr(user, key, str(value) if value is not None else None)
                applied.append(f"{key}={value}")

        # 保存用户
        user = await self._user_repo.save(user)

        # 构建结果
        user_dto = UserDTO(
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
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        if errors and not applied:
            return CommandResult(
                success=False,
                message=f"设置失败: {'; '.join(errors[:3])}",
                data=user_dto,
            )
        elif errors:
            return CommandResult(
                success=True,
                message=f"部分设置成功 ({len(applied)} 项), 失败: {'; '.join(errors[:3])}",
                data=user_dto,
            )
        else:
            return CommandResult(
                success=True,
                message=f"设置成功: {', '.join(applied)}",
                data=user_dto,
            )
