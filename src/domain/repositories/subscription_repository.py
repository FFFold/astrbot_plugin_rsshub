"""
订阅仓库接口

定义订阅实体的持久化操作规范。具体实现由基础设施层提供。
"""

from typing import Protocol

from ..entities.subscription import Subscription


class SubscriptionRepository(Protocol):
    """
    订阅仓库接口

    定义订阅实体的持久化操作规范。具体实现由基础设施层提供。
    """

    async def get_by_id(self, sub_id: int) -> Subscription | None:
        """
        根据ID获取订阅

        Args:
            sub_id: 订阅唯一标识

        Returns:
            Subscription对象，不存在时返回None
        """
        ...

    async def get_by_user(self, user_id: str) -> list[Subscription]:
        """
        获取用户的所有订阅

        Args:
            user_id: 用户唯一标识

        Returns:
            订阅列表
        """
        ...

    async def get_by_user_and_feed(
        self, user_id: str, feed_id: int
    ) -> Subscription | None:
        """
        根据用户和Feed获取订阅

        Args:
            user_id: 用户唯一标识
            feed_id: Feed唯一标识

        Returns:
            Subscription对象，不存在时返回None
        """
        ...

    async def get_all_active(self) -> list[Subscription]:
        """
        获取所有启用的订阅

        Returns:
            订阅列表
        """
        ...

    async def get_active_by_feed_id(self, feed_id: int) -> list[Subscription]:
        """
        获取指定Feed的所有启用订阅

        Args:
            feed_id: Feed唯一标识

        Returns:
            订阅列表
        """
        ...

    async def save(self, subscription: Subscription) -> Subscription:
        """
        保存订阅

        Args:
            subscription: 订阅实体

        Returns:
            保存后的订阅实体
        """
        ...

    async def delete(self, subscription: Subscription) -> None:
        """
        删除订阅

        Args:
            subscription: 订阅实体
        """
        ...

    async def delete_all_by_user(self, user_id: str) -> int:
        """
        删除用户的所有订阅

        Args:
            user_id: 用户唯一标识

        Returns:
            删除的订阅数量
        """
        ...

    async def update_options(
        self, sub_id: int, user_id: str, **kwargs
    ) -> Subscription | None:
        """
        更新订阅配置选项

        Args:
            sub_id: 订阅唯一标识
            user_id: 用户唯一标识
            **kwargs: 要更新的字段

        Returns:
            更新后的订阅实体，不存在时返回None
        """
        ...
