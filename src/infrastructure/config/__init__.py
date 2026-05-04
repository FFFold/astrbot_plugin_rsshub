"""配置管理包

提供配置加载、验证和访问功能。
"""

from .config_manager import (
    BasicConfig,
    FFmpegConfig,
    GlobalConfig,
    RsshubPluginConfig,
    SenderStrategiesConfig,
    TranslationConfig,
    WebUIConfig,
    get_config,
    get_config_manager,
    set_config,
)

__all__ = [
    "BasicConfig",
    "GlobalConfig",
    "FFmpegConfig",
    "WebUIConfig",
    "TranslationConfig",
    "SenderStrategiesConfig",
    "RsshubPluginConfig",
    "get_config",
    "get_config_manager",
    "set_config",
]
