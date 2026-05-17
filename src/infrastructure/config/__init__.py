"""配置管理包

提供配置加载、验证和访问功能。
"""

from .config_manager import (
    BaiduTranslateConfig,
    BasicConfig,
    FFmpegConfig,
    GlobalConfig,
    GoogleTranslateConfig,
    RsshubPluginConfig,
    SenderStrategiesConfig,
    TranslationConfig,
    get_config,
    get_config_manager,
    set_config,
)

__all__ = [
    "BasicConfig",
    "BaiduTranslateConfig",
    "GlobalConfig",
    "GoogleTranslateConfig",
    "FFmpegConfig",
    "TranslationConfig",
    "SenderStrategiesConfig",
    "RsshubPluginConfig",
    "get_config",
    "get_config_manager",
    "set_config",
]
