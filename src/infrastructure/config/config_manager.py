"""配置管理模块

提供统一的、类型安全的插件配置访问。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from astrbot.api import AstrBotConfig

SENDER_STRATEGY_KEYS: tuple[str, ...] = (
    "telegram",
    "aiocqhttp",
    "qq_official",
    "weixin_oc",
)


class PlatformSenderStrategyConfig(BaseModel):
    """平台专属 sender 策略。"""

    enable_telegraph: bool = Field(default=False, description="启用 Telegraph 自动分流")
    telegraph_token: str = Field(default="", description="Telegraph access token")
    prefer_local_video: bool = Field(
        default=False, description="是否优先使用本地视频文件"
    )

    @classmethod
    def from_dict(cls, data: Any) -> PlatformSenderStrategyConfig:
        if not data:
            return cls()
        if isinstance(data, list):
            data = next((item for item in data if isinstance(item, dict)), None)
        if not isinstance(data, dict):
            return cls()
        clean_data = {k: v for k, v in data.items() if k != "__template_key"}
        return cls.model_validate({**cls().model_dump(), **clean_data})

    def to_template_list(self, template_key: str) -> list[dict[str, Any]]:
        data = self.model_dump()
        if data == type(self)().model_dump():
            return []
        return [{"__template_key": template_key, **data}]


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
    display_author: str = Field(default="自动", description="显示作者")
    display_via: str = Field(default="自动", description="显示来源")
    display_title: str = Field(default="自动", description="显示标题")
    display_entry_tags: bool = Field(default=False, description="显示标签")
    style: str = Field(default="RSStT", description="样式")
    display_media: bool = Field(default=True, description="显示媒体")

    _SEND_MODE_MAP: ClassVar[dict[str, int]] = {"仅链接": -1, "自动": 0, "直接发送": 1}
    _DISPLAY_AUTHOR_MAP: ClassVar[dict[str, int]] = {"禁用": -1, "自动": 0, "强制": 1}
    _DISPLAY_VIA_MAP: ClassVar[dict[str, int]] = {
        "完全禁用": -2,
        "仅链接": -1,
        "自动": 0,
        "强制": 1,
    }
    _DISPLAY_TITLE_MAP: ClassVar[dict[str, int]] = {
        "禁用": -1,
        "自动": 0,
        "强制": 1,
    }
    _STYLE_MAP: ClassVar[dict[str, int]] = {"RSStT": 0, "flowerss": 1}

    _SEND_MODE_RMAP: ClassVar[dict[int, str]] = {-1: "仅链接", 0: "自动", 1: "直接发送"}
    _DISPLAY_AUTHOR_RMAP: ClassVar[dict[int, str]] = {
        -1: "禁用",
        0: "自动",
        1: "强制",
    }
    _DISPLAY_VIA_RMAP: ClassVar[dict[int, str]] = {
        -2: "完全禁用",
        -1: "仅链接",
        0: "自动",
        1: "强制",
    }
    _DISPLAY_TITLE_RMAP: ClassVar[dict[int, str]] = {
        -1: "禁用",
        0: "自动",
        1: "强制",
    }
    _STYLE_RMAP: ClassVar[dict[int, str]] = {0: "RSStT", 1: "flowerss"}

    def to_db_values(self) -> dict[str, Any]:
        """转换为数据库存储的整数值"""
        return {
            "interval": self.interval,
            "notify": 1 if self.notify else 0,
            "send_mode": self._SEND_MODE_MAP.get(self.send_mode, 0),
            "length_limit": self.length_limit,
            "display_author": self._DISPLAY_AUTHOR_MAP.get(self.display_author, 0),
            "display_via": self._DISPLAY_VIA_MAP.get(self.display_via, 0),
            "display_title": self._DISPLAY_TITLE_MAP.get(self.display_title, 0),
            "display_entry_tags": -1 if not self.display_entry_tags else 0,
            "style": self._STYLE_MAP.get(self.style, 0),
            "display_media": -1 if not self.display_media else 0,
        }

    @classmethod
    def normalize_send_mode_value(cls, value: Any) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return 0
        if normalized == 2:
            return 1
        if normalized == 1:
            return 0
        if normalized in {-1, 0}:
            return normalized
        return 0

    @classmethod
    def from_db_values(cls, values: dict[str, Any]) -> GlobalConfig:
        """从数据库整数值创建配置"""
        send_mode_value = cls.normalize_send_mode_value(values.get("send_mode", 0))
        return cls(
            interval=values.get("interval", 10),
            notify=values.get("notify", 1) == 1,
            send_mode=cls._SEND_MODE_RMAP.get(send_mode_value, "自动"),
            length_limit=values.get("length_limit", 0),
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


class SenderStrategiesConfig(BaseModel):
    """发送策略配置"""

    telegram: bool = Field(default=True, description="Telegram策略")
    aiocqhttp: bool = Field(default=True, description="QQ策略")
    qq_official: bool = Field(default=True, description="QQ官方策略")
    weixin_oc: bool = Field(default=True, description="微信策略")
    telegram_settings: PlatformSenderStrategyConfig = Field(
        default_factory=PlatformSenderStrategyConfig, alias="telegram_config"
    )
    aiocqhttp_settings: PlatformSenderStrategyConfig = Field(
        default_factory=PlatformSenderStrategyConfig, alias="aiocqhttp_config"
    )

    @classmethod
    def from_config(cls, data: Any) -> SenderStrategiesConfig:
        if data is None:
            return cls()
        if isinstance(data, dict):
            known_values = dict.fromkeys(SENDER_STRATEGY_KEYS, True)
            if "enabled_platforms" in data:
                enabled = _enabled_from_sender_config(data) or set()
                known_values.update(
                    {key: key in enabled for key in SENDER_STRATEGY_KEYS}
                )
            else:
                known_values.update(
                    {
                        key: bool(value)
                        for key, value in data.items()
                        if key in SENDER_STRATEGY_KEYS and isinstance(value, bool)
                    }
                )
            return cls.model_validate(
                {
                    **known_values,
                    "telegram_config": PlatformSenderStrategyConfig.from_dict(
                        data.get("telegram") or data.get("telegram_config")
                    ),
                    "aiocqhttp_config": PlatformSenderStrategyConfig.from_dict(
                        data.get("aiocqhttp") or data.get("aiocqhttp_config")
                    ),
                }
            )
        if isinstance(data, str):
            parts = data.replace(",", "\n").splitlines()
            enabled = {part.strip() for part in parts if part.strip()}
            return cls.from_enabled_platforms(enabled)
        if isinstance(data, (list, tuple, set)):
            enabled = {str(item).strip() for item in data if str(item).strip()}
            return cls.from_enabled_platforms(enabled)
        return cls.model_validate({**cls().model_dump(), **(data or {})})

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SenderStrategiesConfig:
        return cls.from_config(data)

    @classmethod
    def from_enabled_platforms(cls, enabled: set[str]) -> SenderStrategiesConfig:
        enabled = {item for item in enabled if item in SENDER_STRATEGY_KEYS}
        return cls(**{key: key in enabled for key in SENDER_STRATEGY_KEYS})

    def to_enabled_platforms(self) -> list[str]:
        return [key for key in SENDER_STRATEGY_KEYS if getattr(self, key)]

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "enabled_platforms": self.to_enabled_platforms(),
            "telegram": self.telegram_settings.to_template_list("telegram_strategy"),
            "aiocqhttp": self.aiocqhttp_settings.to_template_list("onebot_strategy"),
        }


def _enabled_from_sender_config(data: dict[str, Any]) -> set[str] | None:
    if "enabled_platforms" in data:
        raw = data.get("enabled_platforms")
        if isinstance(raw, str):
            return {
                part.strip()
                for part in raw.replace(",", "\n").splitlines()
                if part.strip()
            }
        if isinstance(raw, (list, tuple, set)):
            return {str(item).strip() for item in raw if str(item).strip()}
        return set()

    bool_keys = {key for key in SENDER_STRATEGY_KEYS if isinstance(data.get(key), bool)}
    if bool_keys:
        return {key for key in bool_keys if bool(data.get(key))}
    return None


class RouteKnowledgeConfig(BaseModel):
    """RSSHub Routes 知识库同步配置"""

    kb_name: str = Field(default="RSSHub Routes", description="AstrBot 知识库名称")
    embedding_provider_id: str = Field(
        default="", description="默认向量模型 Provider ID"
    )
    rerank_provider_id: str = Field(
        default="", description="默认重排序模型 Provider ID"
    )
    source_mode: str = Field(default="mirror", description="知识库来源模式")
    source_base_url: str = Field(
        default=(
            "https://raw.githubusercontent.com/"
            "FlanChanXwO/rsshub-routes-knowledgebase/main"
        ),
        description="Routes 知识库文件源 base URL",
    )
    fallback_base_url: str = Field(
        default=(
            "https://raw.githubusercontent.com/"
            "FlanChanXwO/rsshub-routes-knowledgebase/main"
        ),
        description="auto 模式下的 fallback base URL",
    )
    local_source_dir: str = Field(default="", description="local 模式本地目录")
    timeout: int = Field(default=30, description="同步请求超时（秒）")
    batch_size: int = Field(default=32, description="KB embedding 批大小")
    tasks_limit: int = Field(default=3, description="KB embedding 并发任务数")
    max_retries: int = Field(default=3, description="KB embedding 最大重试次数")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RouteKnowledgeConfig:
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
    route_knowledge: RouteKnowledgeConfig = Field(default_factory=RouteKnowledgeConfig)
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
        sender_strategies_cfg = astrbot_config.get("sender_strategies")
        route_knowledge_cfg = astrbot_config.get("route_knowledge", {})

        return cls(
            basic_config=BasicConfig.from_dict(basic_cfg),
            global_config=GlobalConfig.from_dict(global_cfg),
            ffmpeg=FFmpegConfig.from_dict(ffmpeg_cfg),
            sender_strategies=SenderStrategiesConfig.from_config(sender_strategies_cfg),
            route_knowledge=RouteKnowledgeConfig.from_dict(route_knowledge_cfg),
            db_file=astrbot_config.get("db_file", "rsshub.db"),
        )

    def save(self, astrbot_config: AstrBotConfig) -> None:
        """保存配置到 AstrBotConfig"""
        config_dict = self.model_dump()
        config_dict["sender_strategies"] = self.sender_strategies.to_config_dict()
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


_config: RsshubPluginConfig | None = None


def get_config() -> RsshubPluginConfig | None:
    """获取插件配置（legacy 兼容入口）。

    优先通过 `set_config()` 在启动阶段注入配置；只有过渡路径和少量
    legacy 调用方才应直接读取这里的全局状态。
    """
    return _config


def get_config_manager() -> RsshubPluginConfig | None:
    """获取插件配置管理器（旧名称，保留兼容）。"""
    return _config


def set_config(config: RsshubPluginConfig) -> None:
    """设置插件配置（启动阶段注入）。"""
    global _config
    _config = config
