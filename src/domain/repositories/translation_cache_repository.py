"""翻译缓存仓库接口

定义翻译缓存实体的持久化操作规范。具体实现由基础设施层提供。
"""

from typing import Protocol

from ..entities.translation_cache import TranslationCache


class TranslationCacheRepository(Protocol):
    """翻译缓存仓库接口

    定义翻译缓存实体的持久化操作规范。具体实现由基础设施层提供。
    """

    async def get_by_id(self, cache_id: int) -> TranslationCache | None:
        """根据ID获取翻译缓存

        Args:
            cache_id: 翻译缓存唯一标识

        Returns:
            TranslationCache对象，不存在时返回None
        """
        ...

    async def get_by_hash(self, hash: str) -> TranslationCache | None:
        """根据哈希获取翻译缓存

        Args:
            hash: 原文哈希

        Returns:
            TranslationCache对象，不存在时返回None
        """
        ...

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[TranslationCache]:
        """获取所有翻译缓存

        Args:
            limit: 限制数量
            offset: 偏移量

        Returns:
            翻译缓存列表
        """
        ...

    async def delete(self, cache_id: int) -> bool:
        """删除翻译缓存

        Args:
            cache_id: 翻译缓存唯一标识

        Returns:
            是否删除成功
        """
        ...

    async def delete_old_records(self, days: int = 30) -> int:
        """删除指定天数前的翻译缓存

        Args:
            days: 保留天数

        Returns:
            删除的记录数量
        """
        ...

    async def get_stats(self) -> dict[str, int]:
        """获取翻译缓存统计信息

        Returns:
            统计信息字典，包含 total
        """
        ...
