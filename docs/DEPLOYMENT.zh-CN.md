# 部署说明

**语言：** [English](DEPLOYMENT.md) | 中文

本文说明如何在本地、Docker 或手工服务模式下运行 `emby-intro-marker-sidecar`。默认你已经 clone 了 GitHub 仓库，并在仓库根目录操作。

## 已经可以使用

- 可对本地媒体库执行 dry-run 分析
- 可先查看候选报告再决定是否写回
- 可通过 Docker 挂载媒体目录和 Emby 配置目录运行
- 可用浏览器或自动化工具调用健康检查和任务接口

## 你需要自己提供

- 你自己的 Emby 服务地址和 API key
- 媒体文件读取权限
- 如启用写回，必须先备份 Emby 数据库
- 按本机路径调整 `.env` 和 volume 映射

## 本地开发

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
# Edit .env and volume paths before first run.
docker compose up --build
```

如果命令里出现 `. .venv/bin/activate`，Windows PowerShell 下请改用 `.venv\Scripts\Activate.ps1`。

## Docker 部署

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8080/health
```

运行 Docker 前，请先检查所有 volume 映射和 `.env`。示例 compose 文件只提供通用起点，需要按你的主机路径和端口修改。

## 手工部署

- 安装 Python 3.11 和 ffmpeg。
- 创建虚拟环境并执行 `pip install -r requirements.txt`。
- 按 `.env.example` 设置环境变量。
- 执行 `uvicorn app.main:app --host 0.0.0.0 --port 8080`。

## 配置检查清单

- `EMBY_BASE_URL`：你的 Emby 地址
- `EMBY_API_KEY`：你的 API key
- `MEDIA_ROOTS`：容器内可见的媒体根目录
- `EMBY_DB_PATH`：容器内可见的 Emby 数据库路径
- `DRY_RUN=true`：查看报告前建议保持开启

## 验证命令

```bash
python -m compileall app
curl http://localhost:8080/health
```

## 生产检查清单

- 真实使用前替换所有占位密钥。
- 私有配置、生成数据、日志、上传文件和产物不要放进 Git。
- 如果服务会被其他设备访问，请放到启用 HTTPS 的反向代理后面。
- 私有 API 暴露到 localhost 以外前，请先增加鉴权。
- 为数据库、状态目录、上传文件和生成产物配置备份。
- 处理安全问题前先阅读 `SECURITY.md`。

## 排障建议

- 先复查 `.env` 和 volume 路径；多数部署问题来自路径或权限。
- 用 `README.md` 里列出的健康检查接口区分进程启动问题和业务问题。
- 修改部署基础设施前，先跑验证命令。
- 让 AI assistant 帮忙时，提供操作系统、运行时版本、完整命令、去敏日志和部署模式。
