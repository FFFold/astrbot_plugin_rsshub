"""主模块集成测试

测试插件主类的初始化和命令集成。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRSSHubPluginIntegration:
    """RSSHubPlugin 集成测试"""

    @pytest.fixture
    def mock_context(self):
        """模拟 AstrBot 上下文"""
        context = MagicMock()
        context.platform_manager = MagicMock()
        context.platform_manager.platform_insts = []
        return context

    @pytest.fixture
    def mock_config(self):
        """模拟 AstrBot 配置"""
        return {
            "rsshub": {
                "db": {"database": "test.db"},
                "basic": {"timeout": 30, "proxy": ""},
                "webui": {"enabled": False},
                "ffmpeg": {"video_transcode": False},
            }
        }

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, mock_context, mock_config):
        """测试插件初始化"""
        with patch("astrbot.api.star.Star") as mock_star:
            mock_star.__init__ = MagicMock(return_value=None)

            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            assert plugin.astrbot_config == mock_config
            assert plugin._scheduler is None
            assert plugin._webui is None

    @pytest.mark.asyncio
    async def test_parse_target_session_current(self, mock_context, mock_config):
        """测试解析目标会话 - current"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            mock_event = MagicMock()
            mock_event.unified_msg_origin = "telegram:Group:12345"

            session, error = plugin._parse_target_session(mock_event, "current")

            assert error is None
            assert session == "telegram:Group:12345"

    @pytest.mark.asyncio
    async def test_parse_target_session_here(self, mock_context, mock_config):
        """测试解析目标会话 - here"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            mock_event = MagicMock()
            mock_event.unified_msg_origin = "qq:Group:67890"

            session, error = plugin._parse_target_session(mock_event, "here")

            assert error is None
            assert session == "qq:Group:67890"

    @pytest.mark.asyncio
    async def test_parse_target_session_full_format(self, mock_context, mock_config):
        """测试解析目标会话 - 完整格式"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            mock_event = MagicMock()

            session, error = plugin._parse_target_session(
                mock_event, "telegram:Channel:channel_name"
            )

            assert error is None
            assert session == "telegram:Channel:channel_name"

    @pytest.mark.asyncio
    async def test_parse_target_session_empty(self, mock_context, mock_config):
        """测试解析目标会话 - 空参数"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            mock_event = MagicMock()
            mock_event.unified_msg_origin = "wechat:Group:abc123"

            session, error = plugin._parse_target_session(mock_event, "")

            assert error is None
            assert session == "wechat:Group:abc123"

    @pytest.mark.asyncio
    async def test_parse_target_session_invalid(self, mock_context, mock_config):
        """测试解析目标会话 - 无效参数"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            mock_event = MagicMock()

            session, error = plugin._parse_target_session(mock_event, "invalid_format")

            assert session is None
            assert error is not None
            assert "无效" in error

    def test_get_bot_self_id_not_found(self, mock_context, mock_config):
        """测试获取 bot self_id - 未找到平台"""
        with patch("astrbot.api.star.Star"):
            from main import RSSHubPlugin

            plugin = RSSHubPlugin(mock_context, mock_config)

            with pytest.raises(RuntimeError) as exc_info:
                plugin._get_bot_self_id("nonexistent_platform")

            assert "未找到平台" in str(exc_info.value)


class TestCommandIntegration:
    """命令集成测试"""

    def test_command_registration(self):
        """测试命令是否正确注册"""
        # 检查 main.py 中是否有所有必要的命令装饰器
        import inspect
        from main import RSSHubPlugin

        methods = [name for name, _ in inspect.getmembers(RSSHubPlugin, predicate=inspect.isfunction)]

        command_methods = [
            "cmd_sub",
            "cmd_unsub",
            "cmd_sub_list",
            "cmd_sub_list_all",
            "cmd_sub_activate",
            "cmd_sub_deactivate",
            "cmd_sub_unsubs",
            "cmd_sub_activate_subs",
            "cmd_sub_deactivate_subs",
            "cmd_sub_export",
            "cmd_sub_import",
            "cmd_sub_set_user",
            "cmd_sub_get_user",
            "cmd_sub_test",
            "cmd_rsshub_search",
            "cmd_rsshub_list_all",
            "cmd_rsshub_activate_all",
            "cmd_rsshub_deactivate_all",
            "cmd_rsshub_delete_all",
            "cmd_rsshub_info",
            "cmd_rsshub_feeds",
        ]

        for cmd in command_methods:
            assert cmd in methods, f"Command method {cmd} not found"

    @pytest.mark.asyncio
    async def test_sub_command_requires_url(self):
        """测试订阅命令需要 URL"""
        # 这是一个行为测试，验证空 URL 会返回错误
        # 实际测试需要完整的 AstrBot 环境
        pass  # 需要集成环境


class TestSchedulerIntegration:
    """调度器集成测试"""

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """测试调度器启动和停止"""
        # 需要完整的插件环境才能测试
        pass  # 需要集成环境


class TestWebUIIntegration:
    """WebUI 集成测试"""

    @pytest.mark.asyncio
    async def test_webui_disabled_by_default(self):
        """测试 WebUI 默认禁用"""
        # 验证配置中 webui.enabled 默认为 False
        pass  # 需要集成环境


class TestConfigurationIntegration:
    """配置集成测试"""

    def test_config_loading(self, mock_config):
        """测试配置加载"""
        from src.infrastructure.config import RsshubPluginConfig

        config = RsshubPluginConfig.from_astrbot_config(mock_config)

        assert config is not None
        assert config.basic_config.timeout == 30
        assert config.webui.enabled is False
