"""去重服务单元测试"""

from __future__ import annotations

import pytest

from src.infrastructure.persistence.deduplication_service import DeduplicationService


class TestDeduplicationService:
    """DeduplicationService 测试类"""

    @pytest.fixture
    def dedup_service(self):
        return DeduplicationService()

    def test_compute_fingerprints_with_dict(self, dedup_service):
        """测试从字典计算指纹"""
        entry = {
            "id": "test-id-123",
            "title": "Test Title",
            "link": "https://example.com/test",
            "summary": "Test summary content",
        }

        fingerprints = dedup_service.compute_fingerprints(entry)

        assert len(fingerprints) >= 2
        # 应该包含稳定身份指纹
        assert any(fp.startswith("sid:") for fp in fingerprints)

    def test_compute_fingerprints_without_id(self, dedup_service):
        """测试无ID条目的指纹计算"""
        entry = {
            "title": "Test Title",
            "link": "https://example.com/test",
            "summary": "Test summary",
        }

        fingerprints = dedup_service.compute_fingerprints(entry)

        assert len(fingerprints) >= 2

    def test_is_duplicate_with_stable_hash(self, dedup_service):
        """测试稳定哈希去重"""
        entry = {
            "id": "unique-id",
            "title": "Test",
            "link": "https://example.com",
        }

        fingerprints = dedup_service.compute_fingerprints(entry)
        stable_hash = next(fp for fp in fingerprints if fp.startswith("sid:"))

        known_hashes = {stable_hash}
        is_dup, confidence = dedup_service.is_duplicate(entry, known_hashes)

        assert is_dup is True
        assert confidence == 1.0

    def test_is_duplicate_new_entry(self, dedup_service):
        """测试新条目不重复"""
        entry = {
            "id": "new-id",
            "title": "New Title",
            "link": "https://example.com/new",
        }

        known_hashes = set()
        is_dup, confidence = dedup_service.is_duplicate(entry, known_hashes)

        assert is_dup is False
        assert confidence == 0.0

    def test_merge_hash_history(self, dedup_service):
        """测试哈希历史合并"""
        old_groups = [["sid:abc123"], ["sid:def456"]]
        new_groups = [["sid:abc123"], ["sid:ghi789"]]

        merged = dedup_service.merge_hash_history(old_groups, new_groups, limit=10)

        assert len(merged) == 3
        # 新哈希应该在前
        assert merged[0] == ["sid:ghi789"]

    def test_merge_hash_history_with_limit(self, dedup_service):
        """测试哈希历史合并限制"""
        old_groups = [[f"sid:{i}"] for i in range(10)]
        new_groups = [[f"sid:new_{i}"] for i in range(10)]

        merged = dedup_service.merge_hash_history(old_groups, new_groups, limit=15)

        assert len(merged) == 15

    def test_resolve_hash_history_limit(self, dedup_service):
        """测试哈希历史限制计算"""
        limit = dedup_service.resolve_hash_history_limit(
            entry_count=100,
            min_limit=200,
            multiplier=2,
            hard_limit=5000,
        )

        assert limit == 200  # max(200, 100*2) = 200, min(200, 5000) = 200

        limit = dedup_service.resolve_hash_history_limit(
            entry_count=200,
            min_limit=200,
            multiplier=2,
            hard_limit=5000,
        )

        assert limit == 400  # max(200, 200*2) = 400

    def test_strip_tracking_params(self, dedup_service):
        """测试去除跟踪参数"""
        url = "https://example.com/article?utm_source=test&fbclid=123&ref=abc"
        cleaned = dedup_service.strip_tracking_params(url)

        assert "utm_source" not in cleaned
        assert "fbclid" not in cleaned
        assert "ref" not in cleaned
