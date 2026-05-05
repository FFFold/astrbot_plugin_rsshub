# 线上运维

## 基本约束

- 只允许重载 `astrbot_plugin_rsshub`。
- 只允许通过 AstrBot 仪表盘 `/api/plugin/reload` 执行热重载。
- 禁止重启容器（若环境允许重启则按实际情况）。

## 常用路径

- 插件目录：`data/plugins/astrbot_plugin_rsshub/`
- 数据目录：`data/plugin_data/astrbot_plugin_rsshub/`
- 数据库文件：`data/plugin_data/astrbot_plugin_rsshub/rsshub.db`
- 配置文件（面板）：`data/config/astrbot_plugin_rsshub_config.json`
- 配置 schema：`_conf_schema.json`

## 单插件热重载

```bash
curl -X POST http://127.0.0.1:6185/api/plugin/reload \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "astrbot_plugin_rsshub"}'
```

正常返回：

```json
{"status": "ok", "message": "重载成功。", "data": {}}
```

## 代码同步

```bash
rsync -av --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache \
  ./astrbot_plugin_rsshub/ user@host:/path/to/plugins/astrbot_plugin_rsshub/
```

更新后执行单插件热重载。

## 配置同步

配置文件位于 `data/config/astrbot_plugin_rsshub_config.json`，更新后同样只需热重载。

## 发布记录

发布版本时需要同时完成：

1. 更新 `metadata.yaml` 版本号。
2. 更新 `CHANGELOG.md`。
3. 提交并推送代码。
4. 创建对应 tag。
5. 发布 GitHub Release。
