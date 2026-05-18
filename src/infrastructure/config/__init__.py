"""配置管理包

提供配置加载、验证和访问功能。
"""

from .config_manager import (
    BasicConfig,
    FFmpegConfig,
    GlobalConfig,
    PipelineFeatureConfig,
    RsshubPluginConfig,
    SenderStrategiesConfig,
    get_config,
    get_config_manager,
    set_config,
)
from .settings_adapter import build_application_settings

__all__ = [
    "BasicConfig",
    "GlobalConfig",
    "PipelineFeatureConfig",
    "FFmpegConfig",
    "SenderStrategiesConfig",
    "RsshubPluginConfig",
    "get_config",
    "get_config_manager",
    "set_config",
    "build_application_settings",
]
