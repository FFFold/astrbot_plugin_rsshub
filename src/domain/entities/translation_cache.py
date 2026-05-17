"""翻译缓存领域实体

记录每次翻译的结果，用于避免重复翻译相同内容。
不包含任何 ORM 或持久化逻辑。
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TranslationCache(BaseModel):
    """翻译缓存领域实体

    记录每次翻译的结果，用于避免重复翻译相同内容。
    """

    id: int | None = Field(default=None, description="数据库ID")
    hash: str = Field(..., max_length=64, description="原文哈希")
    provider: str = Field(..., max_length=32, description="翻译器类型")
    target_lang: str = Field(..., max_length=16, description="目标语言")
    translated_text: str = Field(default="", description="翻译后的文本")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
