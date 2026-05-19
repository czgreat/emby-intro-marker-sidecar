# Emby Intro Marker Sidecar / Emby 片头片尾标记服务

[![CI](https://github.com/czgreat/emby-intro-marker-sidecar/actions/workflows/ci.yml/badge.svg)](https://github.com/czgreat/emby-intro-marker-sidecar/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**语言：** [English](README.md) | 中文

自托管 sidecar 服务，用于检测剧集里重复的片头/片尾片段，并准备 Emby 章节标记。

## 概览

Emby Intro Marker Sidecar 会通过 Emby HTTP API 读取媒体库信息，用 ffmpeg 采样本地媒体音频，比较剧集之间重复的音频指纹，并在明确配置后写入章节标记数据。

## 主要功能

- 通过 Emby API 读取媒体库元数据
- 使用 ffmpeg 采样音频并生成重复指纹
- 跨剧集识别可能的片头和片尾区间
- 提供状态、调度、运行时、报告和任务接口
- 默认建议以 dry-run 模式启动

## 当前公开版状态

已经可以使用：

- 可对本地媒体库执行 dry-run 分析
- 可先查看候选报告再决定是否写回
- 可通过 Docker 挂载媒体目录和 Emby 配置目录运行
- 可用浏览器或自动化工具调用健康检查和任务接口

需要你在本地补全：

- 你自己的 Emby 服务地址和 API key
- 媒体文件读取权限
- 如启用写回，必须先备份 Emby 数据库
- 按本机路径调整 `.env` 和 volume 映射

## 快速开始

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env and volume paths before first run.
docker compose up --build
```

如果在 Windows PowerShell 使用 Python 虚拟环境，请用 `.venv\Scripts\Activate.ps1`，不要用 `. .venv/bin/activate`。

## Docker 部署

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8080/health
```

## 手工部署

- 安装 Python 3.11 和 ffmpeg。
- 创建虚拟环境并执行 `pip install -r requirements.txt`。
- 按 `.env.example` 设置环境变量。
- 执行 `uvicorn app.main:app --host 0.0.0.0 --port 8080`。

## 配置说明

- `EMBY_BASE_URL`：你的 Emby 地址
- `EMBY_API_KEY`：你的 API key
- `MEDIA_ROOTS`：容器内可见的媒体根目录
- `EMBY_DB_PATH`：容器内可见的 Emby 数据库路径
- `DRY_RUN=true`：查看报告前建议保持开启

## API 概览

- `GET /health` 健康检查
- `GET /api/status` 查看运行状态
- `GET /api/reports` 查看报告
- `POST /api/jobs/run-sample` 执行样本任务
- `POST /api/runtime` 调整运行时配置

## 验证命令

```bash
python -m compileall app
curl http://localhost:8080/health
```

## 仓库结构

| 路径 | 说明 |
|---|---|
| `app/main.py` | FastAPI 应用和 HTTP 路由 |
| `app/service.py` | 检测流程编排 |
| `app/detector.py` | 音频片段检测逻辑 |
| `app/emby_client.py` | Emby API 客户端 |
| `app/sqlite_writer.py` | 可选写回路径 |
| `config/` | 检测器和 SQLite 模板示例 |

## 更多文档

| 主题 | 中文 | English |
|---|---|---|
| 部署 | [docs/DEPLOYMENT.zh-CN.md](docs/DEPLOYMENT.zh-CN.md) | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| AI 接手 | [docs/AI_HANDOFF.zh-CN.md](docs/AI_HANDOFF.zh-CN.md) | [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md) |
| 路线图 | [docs/ROADMAP.zh-CN.md](docs/ROADMAP.zh-CN.md) | [docs/ROADMAP.md](docs/ROADMAP.md) |

## AI 辅助开发说明

这个公开版由 Codex 使用 GPT-5.4 和 GPT-5.5 辅助整理完成。源码、文档和公开前清理都经过面向公开分享的复核，但本项目是社区项目，不是 OpenAI 官方产品。

适合继续交给 AI coding assistant 的任务：

- 增加基于 fixture 的检测测试
- 改进报告解释和置信度展示
- 写回前增加安全迁移检查
- 补充不同 Emby 目录布局的部署示例

## 隐私和密钥

不要提交真实 `.env`、API key、webhook secret、cookies、私人媒体、生产数据库、日志、生成产物或个人数据。请从示例配置开始，把私有值保存在 Git 之外。

## License

MIT
