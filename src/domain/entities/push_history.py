"""
推送历史领域实体

记录每次推送的完整信息和状态，用于重试机制和推送统计。
不包含任何 ORM 或持久化逻辑。
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PushHistory(BaseModel):
    """
    推送历史领域实体

    记录每次推送的完整信息和状态，用于重试机制和推送统计。
    """

    id: int | None = Field(default=None, description="数据库ID")
    sub_id: int = Field(..., description="订阅ID")
    user_id: str = Field(..., description="用户ID")
    feed_id: int = Field(..., description="FeedID")

    content: str = Field(default="", description="格式化后的消息内容")
    media_urls: list[str] | None = Field(default=None, description="媒体URL列表")

    entry_title: str = Field(default="", max_length=1024, description="条目标题")
    entry_link: str = Field(default="", max_length=4096, description="条目链接")
    entry_guid: str | None = Field(default=None, max_length=512, description="条目GUID")

    feed_title: str = Field(default="", max_length=1024, description="Feed标题")
    feed_link: str = Field(default="", max_length=4096, description="Feed链接")

    platform_name: str | None = Field(
        default=None, max_length=64, description="平台名称"
    )
    target_session: str | None = Field(
        default=None, max_length=255, description="目标会话"
    )

    status: str | None = Field(
        default=None, max_length=16, description="状态: pending/success/failed"
    )
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    fail_reason: str | None = Field(
        default=None, max_length=512, description="失败原因"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="更新时间"
    )
    completed_at: datetime | None = Field(default=None, description="完成时间")

    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.status == "failed" and self.retry_count < self.max_retries

    def mark_success(self) -> "PushHistory":
        """标记推送成功"""
        self.status = "success"
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        return self

    def record_first_failure(self, reason: str | None = None) -> "PushHistory":
        """记录首次失败（不增加重试计数）"""
        self.status = "failed"
        if reason:
            self.fail_reason = reason
        self.updated_at = datetime.now(timezone.utc)
        return self

    def record_retry_failure(self, reason: str | None = None) -> "PushHistory":
        """记录重试失败（增加重试计数）"""
        self.status = "failed"
        self.retry_count += 1
        if reason:
            self.fail_reason = reason
        self.updated_at = datetime.now(timezone.utc)
        return self

    def mark_retrying(self) -> "PushHistory":
        """标记为正在重试（原子更新用）"""
        self.status = "retrying"
        self.updated_at = datetime.now(timezone.utc)
        return self

    def mark_failed(self, reason: str | None = None) -> "PushHistory":
        """标记推送失败（保持向后兼容，调用 record_first_failure）"""
        return self.record_first_failure(reason)

    def is_pending(self) -> bool:
        """检查是否处于待推送状态"""
        return self.status == "pending"

    def is_success(self) -> bool:
        """检查是否推送成功"""
        return self.status == "success"

    def is_failed(self) -> bool:
        """检查是否推送失败"""
        return self.status == "failed"
