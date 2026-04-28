"""
内容过滤服务

负责过滤和清理 RSS 条目内容，如去重、关键词过滤等。
属于领域服务，因为涉及跨实体的业务逻辑。
"""

from ..entities.feed import Feed


class ContentFilterService:
    """
    内容过滤服务

    负责过滤和清理 RSS 条目内容。
    """

    def is_duplicate(self, feed: Feed, entry_hash: str) -> bool:
        """
        检查条目是否为重复内容

        Args:
            feed: Feed实体
            entry_hash: 条目哈希值

        Returns:
            是否为重复内容
        """
        return feed.has_entry(entry_hash)

    def record_entry(self, feed: Feed, entry_hash: str) -> Feed:
        """
        记录已处理的条目哈希

        Args:
            feed: Feed实体
            entry_hash: 条目哈希值

        Returns:
            更新后的Feed实体
        """
        return feed.add_entry_hash(entry_hash)
