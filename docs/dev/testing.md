# 测试与回归检查

## 基础检查

在 AstrBot 根目录执行：

```bash
uv run ruff format data/plugins/astrbot_plugin_rsshub
uv run ruff check data/plugins/astrbot_plugin_rsshub
```

在插件目录执行：

```bash
pytest tests/ -v
```

或使用分类脚本：

```bash
python tests/run_tests.py --category unit
python tests/run_tests.py --category integration
```

## 建议的分层验证方式

### 改 Python 业务逻辑时

至少做：

- 相关单元测试
- `ruff check`

如果涉及这些链路，建议额外回归：

- `FeedPollingService`
- `NotificationDispatcher`
- Web API
- settings/config adapter
- push history repository

### 改 Plugin Pages 时

至少做：

- `node --check pages/dashboard/app.js`
- `node --check pages/dashboard/js/api.js`

如果改动涉及请求链路，还应手工验证：

- tab 切换
- loading 态
- 批量模式
- 详情面板
- 历史记录筛选

### 改配置或迁移时

重点看：

- 旧配置兼容读取是否还在
- `_conf_schema.json` 是否仍符合约束
- 旧 sqlite / 旧 TOML 是否还能被容忍

## 高风险改动清单

以下改动不要只跑单测：

- 命令签名变化
- sender 行为变化
- push history 字段变化
- handler runtime 行为变化
- 订阅继承规则变化
- Routes KB 同步链路变化

## 回归检查清单

- [ ] `/sub_test` 仍然是真实发送，不是 preview
- [ ] `push_history.content` 不泄漏原始 HTML 标签
- [ ] `raw_xml` 仍保留原始条目 XML
- [ ] `-100` 继承规则没有被破坏
- [ ] OneBot 媒体/文本顺序没有回退
- [ ] Plugin Pages 没有重新暴露 `link_preview`
