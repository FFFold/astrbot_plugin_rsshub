"""
推送历史仓库接口

定义推送历史实体的持久化操作规范。具体实现由基础设施层提供。
"""

from typing import Protocol

from ..entities.push_history import PushHistory


class PushHistoryRepository(Protocol):
    """
    推送历史仓库接口

    定义推送历史实体的持久化操作规范。具体实现由基础设施层提供。
    """

    async def get_by_id(self, history_id: int) -> PushHistory | None:
        """
        根据ID获取推送历史

        Args:
            history_id: 推送历史唯一标识

        Returns:
            PushHistory对象，不存在时返回None
        """
        ...

    async def get_by_sub(
        self, sub_id: int, limit: int | None = None, status: str | None = None
    ) -> list[PushHistory]:
        """
        获取订阅的推送历史

        Args:
            sub_id: 订阅唯一标识
            limit: 限制数量（可选）
            status: 状态过滤（可选）

        Returns:
            推送历史列表
        """
        ...

    async def get_pending_for_retry(self, limit: int = 100) -> list[PushHistory]:
        """
        获取需要重试的推送记录

        Args:
            limit: 限制数量

        Returns:
            需要重试的推送历史列表
        """
        ...

    async def save(self, history: PushHistory) -> PushHistory:
        """
        保存推送历史

        Args:
            history: 推送历史实体

        Returns:
            保存后的推送历史实体
        """
        ...

    async def delete_old_records(self, days: int = 30) -> int:
        """
        删除指定天数前的历史记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数量
        """
        ...

    async def get_stats(self) -> dict[str, int]:
        """
        获取推送统计信息

        Returns:
            统计信息字典，包含 total, pending, success, failed
        """
        ...
