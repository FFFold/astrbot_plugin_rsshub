"""RSSHub 扩展系统

提供扩展注册、管理和执行机制。

扩展可以:
    1. 订阅事件并修改数据
    2. 注册自定义发送器
    3. 添加自定义命令

Examples:
    >>> class MyExtension(Extension):
    ...     @on_event(FeedParseEvent)
    ...     async def modify_entries(self, event: FeedParseEvent):
    ...         # 修改条目
    ...         pass
"""

from __future__ import annotations

import importlib.util
import inspect
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from .event_bus import (
    BaseEvent,
    DeduplicationEvent,
    EntryProcessEvent,
    FeedFetchEvent,
    FeedParseEvent,
    MessageFormatEvent,
    MessageSendEvent,
    MessageSentEvent,
    get_event_bus,
)

if TYPE_CHECKING:
    from ..config import RsshubPluginConfig

T = TypeVar("T", bound=BaseEvent)


class Extension(ABC):
    """RSSHub 扩展基类

    扩展通过继承此类并实现钩子方法来介入处理流程。

    Examples:
        >>> class AIExtension(Extension):
        ...     name = "ai_rewrite"
        ...     version = "1.0.0"
        ...
        ...     async def on_feed_parse(self, event: FeedParseEvent):
        ...         for entry in event.entries:
        ...             entry.title = await self.ai_rewrite(entry.title)
        ...
        ...     async def on_message_format(self, event: MessageFormatEvent):
        ...         event.content = await self.ai_optimize(event.content)
    """

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    priority: int = 100  # 默认优先级，数字越小优先级越高

    def __init__(self) -> None:
        self._registered_handlers: list[tuple[type[BaseEvent], Callable]] = []
        self._event_bus = get_event_bus()

    @property
    def is_enabled(self) -> bool:
        """扩展是否启用（可被配置覆盖）"""
        return True

    def register(self) -> None:
        """注册扩展到事件总线"""
        # 自动注册带有 @on_event 装饰器的方法
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, "_event_type"):
                event_type = method._event_type
                # 使用扩展的优先级
                priority = getattr(self, "priority", 100)
                self._event_bus.on(event_type, priority=priority)(method)
                self._registered_handlers.append((event_type, method))

    def unregister(self) -> None:
        """注销扩展"""
        for event_type, handler in self._registered_handlers:
            self._event_bus.off(event_type, handler)
        self._registered_handlers.clear()

    # 可重写的钩子方法
    async def on_feed_fetch(self, event: FeedFetchEvent) -> None:
        """RSS 抓取后调用"""
        pass

    async def on_feed_parse(self, event: FeedParseEvent) -> None:
        """RSS 解析后调用"""
        pass

    async def on_entry_process(self, event: EntryProcessEvent) -> None:
        """单个条目处理时调用"""
        pass

    async def on_deduplication(self, event: DeduplicationEvent) -> None:
        """去重检查时调用"""
        pass

    async def on_message_format(self, event: MessageFormatEvent) -> None:
        """消息格式化后调用"""
        pass

    async def on_message_send(self, event: MessageSendEvent) -> None:
        """消息发送前调用"""
        pass

    async def on_message_sent(self, event: MessageSentEvent) -> None:
        """消息发送后调用"""
        pass


def on_event(event_type: type[T]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """事件订阅装饰器

    用于在扩展类中标记事件处理方法。

    Examples:
        >>> class MyExtension(Extension):
        ...     @on_event(FeedParseEvent)
        ...     async def modify_entries(self, event: FeedParseEvent):
        ...         pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func._event_type = event_type
        return func

    return decorator


class PluginManager:
    """扩展管理器

    管理扩展的生命周期和加载。支持从配置加载扩展，配置列表顺序决定优先级。

    Examples:
        >>> manager = PluginManager()
        >>> await manager.load_from_config(config)  # 从配置加载
        >>> # 或
        >>> await manager.load_extension("my_extension", "/path/to/my_extension.py")
    """

    def __init__(self, config: RsshubPluginConfig | None = None) -> None:
        self._extensions: dict[str, Extension] = {}
        self._disabled_extensions: set[str] = set()
        self._config = config
        self._logger = get_logger()

    async def load_from_config(
        self, config: RsshubPluginConfig | None = None
    ) -> list[str]:
        """从配置加载扩展，按配置列表顺序注册

        配置列表顺序即为优先级顺序，越靠前优先级越高。
        如果配置列表为空，自动扫描 plugins 目录。

        Args:
            config: 插件配置，None 则使用初始化时传入的配置

        Returns:
            成功加载的扩展名称列表
        """
        cfg = config or self._config
        if cfg is None:
            self._logger.warning("未提供配置，无法加载扩展")
            return []

        loaded: list[str] = []
        extensions_config = getattr(cfg, "basic_config", None)
        extension_names: list[str] = (
            getattr(extensions_config, "extensions", []) if extensions_config else []
        )

        if extension_names:
            # 按配置列表顺序加载
            self._logger.info("从配置加载扩展: %s", extension_names)
            for name in extension_names:
                if await self._load_extension_by_name(name):
                    loaded.append(name)
        else:
            # 配置为空，自动发现
            self._logger.info("配置为空，自动发现扩展...")
            loaded = await self._discover_and_load_extensions()

        return loaded

    async def _load_extension_by_name(self, name: str) -> bool:
        """根据名称加载扩展

        查找路径:
        1. plugins/{name}.py
        2. plugins/{name}/__init__.py

        Args:
            name: 扩展名称

        Returns:
            是否成功加载
        """
        # 获取插件根目录
        from ... import PLUGIN_DIR

        # 尝试直接文件
        ext_path = PLUGIN_DIR / "plugins" / f"{name}.py"
        if ext_path.exists():
            extension = await self.load_extension(name, ext_path)
            return extension is not None

        # 尝试包形式
        ext_pkg_path = PLUGIN_DIR / "plugins" / name / "__init__.py"
        if ext_pkg_path.exists():
            extension = await self.load_extension(name, ext_pkg_path)
            return extension is not None

        self._logger.warning("未找到扩展: %s", name)
        return False

    async def _discover_and_load_extensions(self) -> list[str]:
        """自动发现并加载 plugins 目录下的所有扩展

        Returns:
            成功加载的扩展名称列表
        """
        from ... import PLUGIN_DIR

        plugins_dir = PLUGIN_DIR / "plugins"
        if not plugins_dir.exists():
            self._logger.debug("plugins 目录不存在: %s", plugins_dir)
            return []

        loaded: list[str] = []

        # 收集所有候选扩展
        candidates: list[tuple[str, Path, int]] = []  # (name, path, priority)

        for item in plugins_dir.iterdir():
            if (
                item.is_file()
                and item.suffix == ".py"
                and not item.name.startswith("_")
            ):
                # 单文件扩展
                name = item.stem
                candidates.append((name, item, 100))
            elif item.is_dir() and (item / "__init__.py").exists():
                # 包形式扩展
                name = item.name
                candidates.append((name, item / "__init__.py", 100))

        # 按名称排序，确保确定性加载顺序
        candidates.sort(key=lambda x: x[0])

        for name, path, priority in candidates:
            extension = await self.load_extension(name, path)
            if extension:
                # 设置优先级
                extension.priority = priority
                loaded.append(name)

        return loaded

    async def load_extension(self, name: str, path: str | Path) -> Extension | None:
        """从文件加载扩展

        Args:
            name: 扩展名称
            path: 扩展文件路径

        Returns:
            加载的扩展实例，失败时返回 None
        """
        try:
            spec = importlib.util.spec_from_file_location(name, Path(path))
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找扩展类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Extension)
                    and attr is not Extension
                ):
                    extension = attr()
                    self._extensions[name] = extension
                    self._logger.debug("扩展类 %s 已加载", name)
                    return extension

            # 查找扩展实例（向后兼容）
            for attr_name in ["extension_instance", "plugin_instance"]:
                if hasattr(module, attr_name):
                    instance = getattr(module, attr_name)
                    if isinstance(instance, Extension):
                        self._extensions[name] = instance
                        self._logger.debug("扩展实例 %s 已加载", name)
                        return instance

        except Exception as e:
            self._logger.exception("加载扩展 %s 失败: %s", name, e)

        return None

    def register_extension(self, extension: Extension, name: str | None = None) -> None:
        """注册扩展示例

        Args:
            extension: 扩展示例
            name: 扩展名称，None 则使用 extension.name 或类名
        """
        ext_name = name or extension.name or extension.__class__.__name__
        self._extensions[ext_name] = extension
        if ext_name not in self._disabled_extensions and extension.is_enabled:
            extension.register()
            self._logger.debug("扩展 %s 已注册", ext_name)

    def enable_extension(self, name: str) -> bool:
        """启用扩展"""
        if name not in self._extensions:
            return False

        self._disabled_extensions.discard(name)
        extension = self._extensions[name]
        if extension.is_enabled:
            extension.register()
        return True

    def disable_extension(self, name: str) -> bool:
        """禁用扩展"""
        if name not in self._extensions:
            return False

        self._disabled_extensions.add(name)
        self._extensions[name].unregister()
        return True

    def get_extension(self, name: str) -> Extension | None:
        """获取扩展示例"""
        return self._extensions.get(name)

    def list_extensions(self) -> list[tuple[str, Extension, bool]]:
        """列出所有扩展

        Returns:
            [(名称, 扩展实例, 是否启用), ...]
        """
        return [
            (
                name,
                extension,
                name not in self._disabled_extensions and extension.is_enabled,
            )
            for name, extension in self._extensions.items()
        ]

    def get_enabled_extensions(self) -> list[tuple[str, Extension]]:
        """获取已启用的扩展列表，按优先级排序

        Returns:
            [(名称, 扩展实例), ...]，按优先级排序
        """
        enabled = [
            (name, ext)
            for name, ext in self._extensions.items()
            if name not in self._disabled_extensions and ext.is_enabled
        ]
        # 按优先级排序（数字小的在前）
        enabled.sort(key=lambda x: getattr(x[1], "priority", 100))
        return enabled


# 全局扩展管理器
_plugin_manager: PluginManager | None = None


def get_plugin_manager(config: RsshubPluginConfig | None = None) -> PluginManager:
    """获取全局扩展管理器

    Args:
        config: 可选的配置对象，首次调用时传入

    Returns:
        PluginManager 实例
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(config)
    return _plugin_manager


def reset_plugin_manager() -> None:
    """重置扩展管理器（主要用于测试）"""
    global _plugin_manager
    _plugin_manager = None


# 延迟导入避免循环依赖
from ..utils import get_logger


__all__ = [
    # Extension Base
    "Extension",
    "on_event",
    # Plugin Manager
    "PluginManager",
    "get_plugin_manager",
    "reset_plugin_manager",
]
