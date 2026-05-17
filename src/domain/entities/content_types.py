"""内容类型领域实体

定义消息内容的结构化类型。
"""

from __future__ import annotations

from abc import ABC

from pydantic import BaseModel, Field


class ContentNode(BaseModel, ABC):
    """内容节点基类"""

    def get_plain(self) -> str:
        """获取纯文本表示"""
        raise NotImplementedError


class TextContent(ContentNode):
    """文本内容节点"""

    text: str = Field(..., description="文本内容")

    def get_plain(self) -> str:
        return self.text


class LinkContent(ContentNode):
    """链接内容节点"""

    text: str = Field(default="", description="链接文本")
    url: str = Field(..., description="链接URL")

    def get_plain(self) -> str:
        return self.text


class ImageContent(ContentNode):
    """图片内容节点"""

    url: str = Field(..., description="图片URL")
    alt: str = Field(default="", description="替代文本")

    def get_plain(self) -> str:
        return (self.alt or "").strip()


class VideoContent(ContentNode):
    """视频内容节点"""

    url: str = Field(..., description="视频URL")

    def get_plain(self) -> str:
        return "[视频]"


class AudioContent(ContentNode):
    """音频内容节点"""

    url: str = Field(..., description="音频URL")

    def get_plain(self) -> str:
        return "[音频]"


class FileContent(ContentNode):
    """文件内容节点"""

    url: str = Field(..., description="文件URL")
    name: str = Field(default="", description="文件名")

    def get_plain(self) -> str:
        return f"[文件: {self.name}]" if self.name else "[文件]"


class MentionContent(ContentNode):
    """提及内容节点"""

    target: str = Field(..., description="提及目标")
    name: str = Field(default="", description="提及名称")

    def get_plain(self) -> str:
        return f"@{self.name}" if self.name else "@"


# 内容节点联合类型
ContentNodeType = (
    TextContent
    | LinkContent
    | ImageContent
    | VideoContent
    | AudioContent
    | FileContent
    | MentionContent
)


class HtmlNode(BaseModel):
    """HTML节点"""

    children: list[ContentNodeType | HtmlNode] = Field(default_factory=list)

    def get_plain(self) -> str:
        return "".join(child.get_plain() for child in self.children)


class ParsedResult(BaseModel):
    """HTML解析结果"""

    html_tree: HtmlNode = Field(..., description="解析后的HTML树")
    media: list[ImageContent | VideoContent | AudioContent | FileContent] = Field(
        default_factory=list, description="媒体列表"
    )
    links: list[str] = Field(default_factory=list, description="链接列表")
    mentions: list[MentionContent] = Field(default_factory=list, description="提及列表")
