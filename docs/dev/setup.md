# 开发环境与本地调试

## 前置要求

- Python 3.12+
- AstrBot 主仓库本地开发环境
- 推荐使用 `uv`

## 本地代码位置

插件通常位于：

```text
AstrBot/data/plugins/astrbot_plugin_rsshub
```

## 常用目录

```text
assets/      # 静态资源与帮助图模板
pages/       # Plugin Pages 前端
src/         # DDD 主代码
tests/       # 单元与集成测试
docs/        # 项目、开发、使用文档
skills/      # 给 AI agent 的 skill
```

## 运行与调试原则

### 数据目录

不要把运行时数据写回插件仓库下的 `data/`。

本插件统一通过路径工具访问：

- `get_plugin_data_dir()`
- `get_plugin_cache_dir()`
- `get_plugin_export_dir()`

### 启动结构

- `main.py` 只负责注册和生命周期入口
- `bootstrap.py` 负责装配依赖与 runtime

本地调试时不要把 startup ownership 挪回 `main.py`。

### Plugin Pages

前端位于 `pages/dashboard/`，主要由：

- `index.html`
- `app.js`
- `js/api.js`
- `css/*.css`

构成。前端行为依赖 AstrBot Plugin Pages bridge，不是一个独立 SPA。

## 常用命令

在 AstrBot 根目录执行：

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

在插件目录可执行：

```bash
python tests/run_tests.py -v
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
pytest tests/ -v
```

前端脚本语法可直接检查：

```bash
node --check pages/dashboard/app.js
node --check pages/dashboard/js/api.js
```

## 改动前先确认的几件事

- 改的是命令语义、配置模型，还是 UI 行为？
- 这次改动是否会影响 `push_history` 或 sender 兼容性？
- 这次改动是否需要同步更新 README 与 docs？
