"""消息格式化器

统一各平台消息组件（图片/文字/音频/文件）的排序规则。
senders 只管发送，排序逻辑全部集中在 Formatter 中。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

if TYPE_CHECKING:
    from ..messaging.senders.types import PreparedMedia


class MessageChainFormatter:
    """消息链格式化器

    根据平台特性将预处理后的媒体和文本组合为最终消息链。
    排序规则统一在此管理，senders 只调用 build_chain() 后发送。
    """

    def build_chain(
        self,
        prepared_media: list[PreparedMedia] | None,
        text: str,
        failed_urls: list[str],
        platform: str = "",
    ) -> list:
        """
        构建最终消息链

        Args:
            prepared_media: 预处理后的媒体列表
            text: 文本内容
            failed_urls: 下载失败的媒体 URL 列表（可为空，内部会从 prepared_media 补充）
            platform: 平台名称（onebot/telegram/qidian/...）

        Returns:
            已排好序的消息链 list，可直接传入 MessageChain
        """
        # 自动从 prepared_media 中收集 download_failed 的 URL
        if failed_urls is None:
            failed_urls = []
        if prepared_media:
            for item in prepared_media:
                if item.download_failed and item.original_url not in failed_urls:
                    failed_urls.append(item.original_url)

        if platform == "telegram":
            return self._build_telegram_chain(prepared_media, text, failed_urls)
        return self._build_default_chain(prepared_media, text, failed_urls)

    @staticmethod
    def collect_original_urls(
        prepared_media: list[PreparedMedia] | None,
    ) -> list[str]:
        """Collect all original media URLs in first-seen order."""
        if not prepared_media:
            return []
        urls: list[str] = []
        seen: set[str] = set()
        for item in prepared_media:
            url = str(item.original_url or "").strip()
            if url and url not in seen:
                urls.append(url)
                seen.add(url)
        return urls

    # ------------------------------------------------------------------
    # 通用顺序：images → Plain → tails
    # ------------------------------------------------------------------

    def _build_default_chain(
        self,
        prepared_media: list[PreparedMedia] | None,
        text: str,
        failed_urls: list[str],
    ) -> list:
        """通用消息链顺序：images → Plain → tails"""
        from astrbot.api.message_components import File, Image, Plain, Record, Video

        chain: list = []
        tails: list = []

        if prepared_media:
            for item in prepared_media:
                path = str(item.local_path) if item.local_path else item.original_url
                match item.media_type:
                    case "image":
                        chain.append(Image(file=path))
                    case "video":
                        chain.append(Video(file=path))
                    case "audio":
                        tails.append(Record(file=path, text="audio"))
                    case "file":
                        filename = (
                            unquote(urlparse(item.original_url).path.rsplit("/", 1)[-1])
                            or "attachment"
                        )
                        tails.append(
                            File(name=filename, file=path, url=item.original_url)
                        )

        final_text = self._append_failed_links(text, failed_urls)

        if final_text:
            chain.append(Plain(final_text))
        chain.extend(tails)

        return chain

    # ------------------------------------------------------------------
    # Telegram：media → caption（含失败链接）→ tails
    # ------------------------------------------------------------------

    def _build_telegram_chain(
        self,
        prepared_media: list[PreparedMedia] | None,
        text: str,
        failed_urls: list[str],
    ) -> list:
        """Telegram 消息链：media → Plain(caption) → tails"""
        from astrbot.api.message_components import File, Image, Plain, Record, Video

        chain: list = []
        tails: list = []
        has_media = False

        if prepared_media:
            for item in prepared_media:
                if not item.local_path and not item.original_url:
                    continue
                path = str(item.local_path) if item.local_path else item.original_url
                match item.media_type:
                    case "image":
                        chain.append(Image(file=path))
                        has_media = True
                    case "video":
                        chain.append(Video(file=path))
                        has_media = True
                    case "audio":
                        tails.append(Record(file=path, text="audio"))
                    case "file":
                        filename = (
                            unquote(urlparse(item.original_url).path.rsplit("/", 1)[-1])
                            or "attachment"
                        )
                        tails.append(
                            File(name=filename, file=path, url=item.original_url)
                        )

        if has_media:
            caption = text if text else ""
            if failed_urls:
                caption = self._append_failed_links(caption, failed_urls)
            if caption:
                chain.append(Plain(caption))
        else:
            # 无媒体时退化为通用顺序
            final_text = self._append_failed_links(text, failed_urls)
            if final_text:
                chain.append(Plain(final_text))

        chain.extend(tails)
        return chain

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _append_failed_links(text: str, failed_urls: list[str]) -> str:
        """将下载失败的媒体链接追加到文本末尾"""
        if not failed_urls:
            return text
        unique: list[str] = []
        seen: set[str] = set()
        for url in failed_urls:
            if url and url not in seen:
                unique.append(url)
                seen.add(url)
        if not unique:
            return text
        lines = [text] if text else []
        lines.append("媒体原始链接:")
        lines.extend(unique)
        return "\n".join(lines)


# 兼容旧导入名；新代码优先使用 MessageChainFormatter。
MessageFormatter = MessageChainFormatter
