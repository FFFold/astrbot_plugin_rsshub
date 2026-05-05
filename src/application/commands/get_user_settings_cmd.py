"""获取用户设置命令

处理获取用户默认设置的业务用例。
"""

from __future__ import annotations

from ...domain.repositories.user_repository import UserRepository
from ..dto.result_dto import CommandResult
from ..dto.user_dto import UserDTO


class GetUserSettingsCommand:
    """获取用户设置命令

    处理获取用户默认设置的业务用例。
    """

    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def execute(
        self,
        user_id: str,
    ) -> CommandResult:
        """执行获取用户设置命令

        Args:
            user_id: 用户 ID

        Returns:
            CommandResult: 命令执行结果
        """
        user = await self._user_repo.get_by_id(user_id)

        if not user:
            return CommandResult(
                success=False,
                message=f"用户不存在 (ID: {user_id})",
            )

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

        return CommandResult(
            success=True,
            message="获取用户设置成功",
            data=user_dto,
        )
