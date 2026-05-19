# Emby Intro Marker Sidecar / Emby 片头片尾标记服务

[English](README.md) | [中文](README.zh-CN.md)

这是一个自托管 sidecar 服务，用于分析本地媒体音频，并为 Emby 兼容媒体库生成片头/片尾章节标记。它适合希望保持流程透明、可审计的 homelab 用户。


## AI 辅助开发说明

这个公开版由 Codex 在 GPT-5.4 / GPT-5.5 辅助下整理完成。代码、文档和公开前清理已按公开仓库标准处理，但本项目不是 OpenAI 官方产品。


## 它能做什么

- 通过 Emby HTTP API 读取媒体库信息
- 使用 `ffmpeg` 抽取音频样本
- 对多集内容做重复音频指纹聚类
- 识别可能的 OP / ED 片段
- 默认可以先 dry-run，不写入数据库
- 明确配置后可写入 Emby SQLite 数据库

## 安全模型

如果启用写回，本项目可能修改 Emby 数据库。请始终先使用：

```env
DRY_RUN=true
```

启用写回前务必备份 Emby 数据库。媒体目录建议只读挂载。

## 快速开始

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# 先编辑 .env 和 volume 路径
docker compose up --build
```

健康检查：

```bash
curl http://localhost:8080/health
```

## 配置

核心配置在 `.env`：

- `EMBY_BASE_URL`
- `EMBY_API_KEY`
- `MEDIA_ROOTS`
- `EMBY_DB_PATH`
- `DRY_RUN`
- `RUN_MODE`

`config/` 中保留了可参考的 YAML 示例。

## 开发

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m compileall app
```

## License

MIT

## 更多文档

- [部署说明](docs/DEPLOYMENT.md)
- [AI 接手说明](docs/AI_HANDOFF.md)
- [路线图](docs/ROADMAP.md)

