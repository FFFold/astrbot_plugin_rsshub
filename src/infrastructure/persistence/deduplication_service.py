"""去重服务模块

提供 RSS 条目去重功能，支持多种去重策略。
"""

from __future__ import annotations

import hashlib
import zlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..rss.rss_parser import EntryParsed


class DeduplicationService:
    """条目去重服务

    支持多种去重策略：
    1. Entry ID 去重 - 使用条目的 id/guid
    2. URL 去重 - 去除跟踪参数后的链接
    3. 内容哈希去重 - 基于标题和摘要
    4. 多哈希指纹 - 组合多种指纹提高准确性
    """

    def __init__(self) -> None:
        self._known_hashes: set[str] = set()
        self._tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "utm_id",
            "gclid",
            "fbclid",
            "mc_cid",
            "mc_eid",
            "spm",
            "ref",
            "ref_src",
        }

    def compute_fingerprints(
        self,
        entry: "EntryParsed | dict[str, Any]",
        feed_link: str | None = None,
    ) -> list[str]:
        """计算条目的去重指纹列表

        Returns:
            指纹列表，按优先级排序：
            1. sid:xxx - 稳定身份指纹（基于 id/guid）
            2. content_hash - 内容哈希
            3. upstream_crc - 上游 CRC32
            4. legacy_crc - 遗留 CRC32
        """
        from .rss_parser import RSSParser

        fingerprints = []

        # 提取基础信息
        if isinstance(entry, dict):
            entry_id = str(entry.get("id") or entry.get("guid") or "").strip()
            link = str(entry.get("link") or "").strip()
            title = str(entry.get("title") or "").strip()
            summary = str(entry.get("summary") or entry.get("description") or "").strip()
            published = str(entry.get("published") or "").strip()
        else:
            entry_id = entry.entry_id or entry.guid
            link = entry.link
            title = entry.title
            summary = entry.summary
            published = str(entry.published) if entry.published else ""

        # 1. 稳定身份指纹（sid:xxx）
        stable_material = self._build_stable_material(
            entry_id, link, title, summary
        )
        if stable_material:
            stable_hash = hashlib.sha256(
                stable_material.encode()
            ).hexdigest()
            fingerprints.append(f"sid:{stable_hash}")

        # 2. 内容哈希
        content_material = f"v3|title={title}|link={link}|summary={summary[:512]}"
        content_hash = hashlib.sha256(content_material.encode()).hexdigest()
        fingerprints.append(content_hash)

        # 3. 上游 CRC32
        upstream_material = self._build_upstream_material(entry)
        if upstream_material:
            upstream_crc = hex(zlib.crc32(
                upstream_material.encode("utf-8", errors="ignore")
            ))[2:]
            fingerprints.append(upstream_crc)

        # 4. 遗留 CRC32（向后兼容）
        legacy_hash = self._legacy_crc32(link, title, published)
        if legacy_hash:
            fingerprints.append(legacy_hash)

        return fingerprints

    def _build_stable_material(
        self,
        entry_id: str,
        link: str,
        title: str,
        summary: str,
    ) -> str:
        """构建稳定身份材料"""
        if entry_id:
            return f"v3|id={entry_id}"
        elif link:
            return f"v3|link={link}"
        elif title:
            return f"v3|title={title}"
        elif summary:
            return f"v3|summary={summary[:256]}"
        return ""

    def _build_upstream_material(self, entry: "EntryParsed | dict") -> str:
        """构建上游兼容材料"""
        if isinstance(entry, dict):
            guid = str(entry.get("guid") or "").strip()
            link = str(entry.get("link") or "").strip()
            title = str(entry.get("title") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            content_items = entry.get("content") or []
        else:
            guid = entry.guid or ""
            link = entry.link
            title = entry.title
            summary = entry.summary
            content_items = []

        first_content_value = ""
        if isinstance(content_items, list):
            for content in content_items:
                if isinstance(content, dict):
                    value = content.get("value")
                    if value:
                        first_content_value = str(value).strip()
                        break

        return "\n".join([guid, link, title, summary, first_content_value])

    @staticmethod
    def _legacy_crc32(link: str, title: str, published: str) -> str:
        """计算遗留 v1 指纹（向后兼容）"""
        hash_base = f"{link}{title}{published}"
        return str(zlib.crc32(hash_base.encode()))

    def strip_tracking_params(self, url: str) -> str:
        """去除 URL 中的跟踪参数"""
        from urllib.parse import parse_qsl, urlencode

        # 简单处理：分割 query string
        if "?" not in url:
            return url

        base, query = url.split("?", 1)
        query_pairs = []
        for key, value in parse_qsl(query, keep_blank_values=True):
            if key.lower() not in self._tracking_params:
                query_pairs.append((key, value))

        if query_pairs:
            query_pairs.sort(key=lambda item: item[0].lower())
            new_query = urlencode(query_pairs, doseq=True)
            return f"{base}?{new_query}"
        return base

    def is_duplicate(
        self,
        entry: "EntryParsed | dict[str, Any]",
        known_hashes: set[str],
        feed_link: str | None = None,
    ) -> tuple[bool, float]:
        """检查条目是否重复

        Args:
            entry: 待检查条目
            known_hashes: 已知哈希集合
            feed_link: Feed 链接（用于处理相对链接）

        Returns:
            (是否重复, 置信度 0.0-1.0)
            - 发现稳定身份指纹（sid:xxx）匹配：置信度 1.0
            - 发现内容哈希匹配：置信度 0.9
            - 发现其他指纹匹配：置信度 0.7
            - 未发现匹配：置信度 0.0
        """
        fingerprints = self.compute_fingerprints(entry, feed_link)

        if not fingerprints:
            return False, 0.0

        # 检查稳定身份指纹（最高优先级）
        stable_hash = next(
            (h for h in fingerprints if h.startswith("sid:")), None
        )
        if stable_hash and stable_hash in known_hashes:
            return True, 1.0

        # 检查内容哈希
        content_hash = next(
            (h for h in fingerprints if len(h) == 64), None  # SHA256 长度
        )
        if content_hash and content_hash in known_hashes:
            return True, 0.9

        # 检查其他指纹
        for fp in fingerprints:
            if fp in known_hashes:
                return True, 0.7

        return False, 0.0

    def merge_hash_history(
        self,
        old_hashes: list[list[str]],
        new_hashes: list[list[str]],
        limit: int = 5000,
    ) -> list[list[str]]:
        """合并新旧哈希历史

        Args:
            old_hashes: 旧哈希分组列表
            new_hashes: 新哈希分组列表
            limit: 最大保留数量

        Returns:
            合并后的哈希列表
        """
        merged = []
        seen_identity = set()

        # 优先保留新哈希
        for group in new_hashes + old_hashes:
            if not group:
                continue
            # 查找身份指纹
            identity = next(
                (h for h in group if h.startswith("sid:")), None
            )
            if identity and identity in seen_identity:
                continue
            if identity:
                seen_identity.add(identity)
            merged.append(group)
            if len(merged) >= limit:
                break

        return merged

    def resolve_hash_history_limit(
        self,
        entry_count: int,
        min_limit: int = 200,
        multiplier: int = 2,
        hard_limit: int = 5000,
    ) -> int:
        """计算哈希历史限制

        Args:
            entry_count: 条目数量
            min_limit: 最小限制
            multiplier: 乘数
            hard_limit: 硬限制

        Returns:
            计算后的限制值
        """
        import math

        # 确保参数在合理范围内
        min_limit = min(min_limit, 20000)  # 绝对最大值
        multiplier = min(multiplier, 20000)
        hard_limit = min(hard_limit, 20000)
        hard_limit = max(hard_limit, min_limit)

        # 计算增长限制
        growth_limit = max(entry_count, 1) * multiplier
        return min(max(min_limit, growth_limit), hard_limit)
