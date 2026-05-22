"""
更新订阅选项命令

处理更新订阅配置选项的业务用例。
"""

from ...domain.entities.handlers import parse_handlers_input
from ...domain.entities.subscription import SUPPORTED_HANDLERS_MODES
from ...domain.repositories.subscription_repository import SubscriptionRepository
from ...infrastructure.config import validate_interval_value
from ..dto.result_dto import CommandResult
from ..dto.subscription_dto import SubscriptionDTO

REMOVED_OPTIONS = {
    "translate",
    "translate_target_lang",
    "use_sub_config",
    "ai_prompt",
}
STRING_OPTIONS = {
    "title",
    "tags",
    "target_session",
    "platform_name",
    "handlers_mode",
}
JSON_OPTIONS = {"handlers"}


class UpdateSubscriptionCommand:
    """
    更新订阅选项命令

    处理更新订阅配置选项的业务用例。
    """

    def __init__(self, subscription_repo: SubscriptionRepository):
        self._subscription_repo = subscription_repo

    async def execute(
        self,
        sub_id: int,
        user_id: str,
        **options,
    ) -> CommandResult:
        """
        执行更新命令

        Args:
            sub_id: 订阅 ID
            user_id: 用户 ID
            **options: 要更新的选项

        Returns:
            CommandResult: 命令执行结果
        """
        removed = sorted(REMOVED_OPTIONS.intersection(options))
        if removed:
            return CommandResult(
                success=False,
                message=("订阅翻译选项已移除: " + ", ".join(removed)),
            )
        normalized_options = {}
        for key, value in options.items():
            if key in STRING_OPTIONS:
                normalized_value = str(value or "").strip()
                if key == "handlers_mode":
                    normalized_value = normalized_value.lower()
                    if normalized_value not in SUPPORTED_HANDLERS_MODES:
                        return CommandResult(
                            success=False,
                            message="handlers_mode 只支持 inherit / override / disabled",
                        )
                normalized_options[key] = normalized_value
                continue
            if key in JSON_OPTIONS:
                try:
                    normalized_options[key] = parse_handlers_input(value)
                except ValueError as exc:
                    return CommandResult(success=False, message=str(exc))
                continue
            if key == "interval":
                try:
                    normalized_options[key] = validate_interval_value(
                        value,
                        allow_inherit=True,
                        field_name="interval",
                    )
                except ValueError as exc:
                    return CommandResult(success=False, message=str(exc))
                continue
            normalized_options[key] = value

        subscription = await self._subscription_repo.update_options(
            sub_id, user_id, **normalized_options
        )
        if not subscription:
            return CommandResult(
                success=False,
                message=f"订阅不存在或无权修改 (ID: {sub_id})",
            )

        return CommandResult(
            success=True,
            message=f"已更新订阅选项 (ID: {sub_id})",
            data=SubscriptionDTO(
                id=subscription.id,
                user_id=subscription.user_id,
                feed_id=subscription.feed_id,
                title=subscription.title,
                tags=subscription.tags,
                target_session=subscription.target_session,
                platform_name=subscription.platform_name,
                state=subscription.state,
                created_at=subscription.created_at,
                updated_at=subscription.updated_at,
            ),
        )
