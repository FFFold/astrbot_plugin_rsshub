"""配置管理模块

提供统一的、类型安全的插件配置访问。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig


class BasicConfig(BaseModel):
    """基础设施配置（系统级，不继承）"""

    proxy: str = Field(default="", description="代理地址")
    rsshub_base_url: str = Field(
        default="https://rsshub.app", description="RSSHub基础URL"
    )
    timeout: int = Field(default=30, description="请求超时（秒）")
    minimal_interval: int = Field(default=1, description="最小监控间隔（分钟）")
    hash_history_min: int = Field(default=200, description="去重历史最小值")
    hash_history_multiplier: int = Field(default=2, description="去重历史倍数")
    hash_history_hard_limit: int = Field(default=5000, description="去重历史硬上限")
    tracking_query_params: list[str] = Field(
        default_factory=lambda: [
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
        ]
    )
    failed_queue_capacity: int = Field(default=50, description="失败队列容量")
    failed_queue_max_retries: int = Field(default=3, description="失败队列最大重试次数")
    deduplicate_multi_bot: bool = Field(default=True, description="多BOT去重")
    bootstrap_skip_history: bool = Field(default=True, description="首轮跳过历史")
    debug_payload: bool = Field(default=False, description="调试字段")
    history_entry_limit: int = Field(default=0, description="历史条目限制")
    download_media_before_send: bool = Field(default=False, description="先下载后发送")
    download_media_timeout: int = Field(default=30, description="媒体下载超时")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BasicConfig:
        """从字典创建配置"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class GlobalConfig(BaseModel):
    """全局默认配置（订阅级，可继承）"""

    interval: int = Field(default=10, description="监控间隔（分钟）")
    notify: bool = Field(default=True, description="是否通知")
    send_mode: str = Field(default="自动", description="发送模式")
    length_limit: int = Field(default=0, description="长度限制")
    link_preview: str = Field(default="自动", description="链接预览")
    display_author: str = Field(default="自动", description="显示作者")
    display_via: str = Field(default="自动", description="显示来源")
    display_title: str = Field(default="自动", description="显示标题")
    display_entry_tags: bool = Field(default=False, description="显示标签")
    style: str = Field(default="RSStT", description="样式")
    display_media: bool = Field(default=True, description="显示媒体")
    translate: bool = Field(default=False, description="翻译")
    translate_target_lang: str = Field(default="zh-CN", description="翻译目标语言")

    _SEND_MODE_MAP: dict[str, int] = {"仅链接": -1, "自动": 0, "直接消息": 2}
    _LINK_PREVIEW_MAP: dict[str, int] = {"自动": 0, "强制启用": 1}
    _DISPLAY_AUTHOR_MAP: dict[str, int] = {"禁用": -1, "自动": 0, "强制": 1}
    _DISPLAY_VIA_MAP: dict[str, int] = {
        "完全禁用": -2,
        "仅链接": -1,
        "自动": 0,
        "强制": 1,
    }
    _DISPLAY_TITLE_MAP: dict[str, int] = {"禁用": -1, "自动": 0, "强制": 1}
    _STYLE_MAP: dict[str, int] = {"RSStT": 0, "flowerss": 1}

    _SEND_MODE_RMAP: dict[int, str] = {-1: "仅链接", 0: "自动", 2: "直接消息"}
    _LINK_PREVIEW_RMAP: dict[int, str] = {0: "自动", 1: "强制启用"}
    _DISPLAY_AUTHOR_RMAP: dict[int, str] = {-1: "禁用", 0: "自动", 1: "强制"}
    _DISPLAY_VIA_RMAP: dict[int, str] = {
        -2: "完全禁用",
        -1: "仅链接",
        0: "自动",
        1: "强制",
    }
    _DISPLAY_TITLE_RMAP: dict[int, str] = {-1: "禁用", 0: "自动", 1: "强制"}
    _STYLE_RMAP: dict[int, str] = {0: "RSStT", 1: "flowerss"}

    def to_db_values(self) -> dict[str, Any]:
        """转换为数据库存储的整数值"""
        return {
            "interval": self.interval,
            "notify": 1 if self.notify else 0,
            "send_mode": self._SEND_MODE_MAP.get(self.send_mode, 0),
            "length_limit": self.length_limit,
            "link_preview": self._LINK_PREVIEW_MAP.get(self.link_preview, 0),
            "display_author": self._DISPLAY_AUTHOR_MAP.get(self.display_author, 0),
            "display_via": self._DISPLAY_VIA_MAP.get(self.display_via, 0),
            "display_title": self._DISPLAY_TITLE_MAP.get(self.display_title, 0),
            "display_entry_tags": -1 if not self.display_entry_tags else 0,
            "style": self._STYLE_MAP.get(self.style, 0),
            "display_media": -1 if not self.display_media else 0,
            "translate": 1 if self.translate else 0,
            "translate_target_lang": self.translate_target_lang,
        }

    @classmethod
    def from_db_values(cls, values: dict[str, Any]) -> GlobalConfig:
        """从数据库整数值创建配置"""
        return cls(
            interval=values.get("interval", 10),
            notify=values.get("notify", 1) == 1,
            send_mode=cls._SEND_MODE_RMAP.get(values.get("send_mode", 0), "自动"),
            length_limit=values.get("length_limit", 0),
            link_preview=cls._LINK_PREVIEW_RMAP.get(
                values.get("link_preview", 0), "自动"
            ),
            display_author=cls._DISPLAY_AUTHOR_RMAP.get(
                values.get("display_author", 0), "自动"
            ),
            display_via=cls._DISPLAY_VIA_RMAP.get(values.get("display_via", 0), "自动"),
            display_title=cls._DISPLAY_TITLE_RMAP.get(
                values.get("display_title", 0), "自动"
            ),
            display_entry_tags=values.get("display_entry_tags", -1) != -1,
            style=cls._STYLE_RMAP.get(values.get("style", 0), "RSStT"),
            display_media=values.get("display_media", 0) != -1,
            translate=values.get("translate", 0) == 1,
            translate_target_lang=values.get("translate_target_lang", "zh-CN"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GlobalConfig:
        """从字典创建配置（用户友好的格式）"""
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class FFmpegConfig(BaseModel):
    """FFmpeg 配置"""

    video_transcode: bool = Field(default=False, description="视频转码")
    video_transcode_timeout: int = Field(default=120, description="视频转码超时")
    gif_transcode: bool = Field(default=False, description="GIF转码")
    gif_transcode_timeout: int = Field(default=60, description="GIF转码超时")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FFmpegConfig:
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class WebUIConfig(BaseModel):
    """WebUI 配置"""

    enabled: bool = Field(default=False, description="是否启用")
    host: str = Field(default="0.0.0.0", description="监听主机")
    port: int = Field(default=9191, description="监听端口")
    auth_enabled: bool = Field(default=True, description="是否启用认证")
    password: str = Field(default="", description="认证密码")
    session_timeout: int = Field(default=3600, description="会话超时（秒）")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WebUIConfig:
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class TranslationConfig(BaseModel):
    """翻译配置"""

    provider: str = Field(default="google", description="翻译提供商")
    target_lang: str = Field(default="zh-CN", description="目标语言")
    auto_translate: bool = Field(default=False, description="自动翻译")
    force_translate: bool = Field(default=False, description="强制翻译")
    translate_title: bool = Field(default=True, description="翻译标题")
    translate_content: bool = Field(default=True, description="翻译内容")
    display_orignal_content: bool = Field(default=False, description="显示原文")
    cache_translations: bool = Field(default=True, description="缓存翻译")
    translation_template: list[dict[str, Any]] = Field(
        default_factory=list, description="翻译模板"
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TranslationConfig:
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class SenderStrategiesConfig(BaseModel):
    """发送策略配置"""

    telegram: bool = Field(default=True, description="Telegram策略")
    aiocqhttp: bool = Field(default=True, description="QQ策略")
    weixin_oc: bool = Field(default=True, description="微信策略")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SenderStrategiesConfig:
        if not data:
            return cls()
        return cls.model_validate({**cls().model_dump(), **(data or {})})


class RsshubPluginConfig(BaseModel):
    """RSSHub 插件统一配置类"""

    basic_config: BasicConfig = Field(default_factory=BasicConfig)
    global_config: GlobalConfig = Field(default_factory=GlobalConfig)
    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)
    sender_strategies: SenderStrategiesConfig = Field(
        default_factory=SenderStrategiesConfig
    )
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    webui: WebUIConfig = Field(default_factory=WebUIConfig)
    db_file: str = Field(default="rsshub.db", description="数据库文件名")

    @classmethod
    def from_astrbot_config(
        cls, astrbot_config: dict[str, Any] | None
    ) -> RsshubPluginConfig:
        """从 AstrBot 配置字典创建配置对象"""
        if not astrbot_config:
            return cls()

        # 处理旧格式配置迁移
        if (
            "download_image_before_send" in astrbot_config
            and "basic_config" in astrbot_config
        ):
            astrbot_config["basic_config"]["download_media_before_send"] = (
                astrbot_config.pop("download_image_before_send")
            )
        if (
            "m3u8_download_timeout" in astrbot_config
            and "basic_config" in astrbot_config
        ):
            astrbot_config["basic_config"]["download_media_timeout"] = (
                astrbot_config.pop("m3u8_download_timeout")
            )

        basic_cfg = astrbot_config.get("basic_config", {})
        global_cfg = astrbot_config.get("global_config", {})
        ffmpeg_cfg = astrbot_config.get("ffmpeg", {})
        sender_strategies_cfg = astrbot_config.get("sender_strategies", {})
        translation_cfg = astrbot_config.get("translation", {})
        webui_cfg = astrbot_config.get("webui", {})

        return cls(
            basic_config=BasicConfig.from_dict(basic_cfg),
            global_config=GlobalConfig.from_dict(global_cfg),
            ffmpeg=FFmpegConfig.from_dict(ffmpeg_cfg),
            sender_strategies=SenderStrategiesConfig.from_dict(sender_strategies_cfg),
            translation=TranslationConfig.from_dict(translation_cfg),
            webui=WebUIConfig.from_dict(webui_cfg),
            db_file=astrbot_config.get("db_file", "rsshub.db"),
        )

    def save(self, astrbot_config: AstrBotConfig) -> None:
        """保存配置到 AstrBotConfig"""
        config_dict = self.model_dump()
        for key, value in config_dict.items():
            if key != "db_file":
                astrbot_config[key] = value
        astrbot_config.save_config()

    # 向后兼容属性

    @property
    def proxy(self) -> str:
        return self.basic_config.proxy

    @property
    def rsshub_base_url(self) -> str:
        return self.basic_config.rsshub_base_url

    @property
    def timeout(self) -> int:
        return self.basic_config.timeout

    @property
    def minimal_interval(self) -> int:
        return self.basic_config.minimal_interval

    @property
    def hash_history_min(self) -> int:
        return self.basic_config.hash_history_min

    @property
    def hash_history_multiplier(self) -> int:
        return self.basic_config.hash_history_multiplier

    @property
    def hash_history_hard_limit(self) -> int:
        return self.basic_config.hash_history_hard_limit

    @property
    def tracking_query_params(self) -> list[str]:
        return self.basic_config.tracking_query_params

    @property
    def failed_queue_capacity(self) -> int:
        return self.basic_config.failed_queue_capacity

    @property
    def failed_queue_max_retries(self) -> int:
        return self.basic_config.failed_queue_max_retries

    @property
    def deduplicate_multi_bot(self) -> bool:
        return self.basic_config.deduplicate_multi_bot

    @property
    def bootstrap_skip_history(self) -> bool:
        return self.basic_config.bootstrap_skip_history

    @property
    def debug_payload(self) -> bool:
        return self.basic_config.debug_payload

    @property
    def history_entry_limit(self) -> int:
        return self.basic_config.history_entry_limit

    @property
    def default_interval(self) -> int:
        return self.global_config.interval

    @property
    def download_media_before_send(self) -> bool:
        return self.basic_config.download_media_before_send

    @property
    def download_media_timeout(self) -> int:
        return self.basic_config.download_media_timeout

    @property
    def download_image_before_send(self) -> bool:
        """向后兼容旧名称"""
        return self.basic_config.download_media_before_send
