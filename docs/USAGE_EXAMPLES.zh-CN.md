# 使用和 API 示例

**语言：** [English](USAGE_EXAMPLES.md) | 中文

这些示例使用公开安全的占位数据。复制到自己的环境前，请替换 URL、token、路径和配置，并确认你有权处理对应数据。

## 示例 1：健康检查和状态

先用健康检查/状态接口确认配置，再启动媒体扫描。

## 示例 2：dry-run 样本扫描

保持 `DRY_RUN=true`，执行样本任务，再复核报告，之后再考虑调整写回配置。

## curl 示例

```bash
curl http://localhost:8080/health
curl http://localhost:8080/api/status
curl -X POST http://localhost:8080/api/jobs/run-sample
curl http://localhost:8080/api/reports
```

接口请求体会随版本变化；以本地 `/docs` 或源码里的模型定义为准。


## 本地验证建议

- 先按 `README.zh-CN.md` 启动项目。
- 先调用健康检查，再执行会写入状态或发通知的操作。
- 使用合成数据或公开演示数据，不要把私人数据写进 issue、截图或提交。
- 如果让 AI assistant 帮忙，把本文件、部署文档和已去敏日志一起提供给它。
