[English](./README.md) | 中文

# MultiGen - 通用 AI Agent 系统

MultiGen 是一个通用的 AI Agent 系统，支持完全私有化部署，使用 A2A + MCP 连接 Agent/Tool，同时支持在沙箱中运行各种内置工具和操作。

## 项目结构

```
mooc-manus/
├── api/              # 后端 API 服务（FastAPI）
├── ui/               # 前端服务（Next.js）
├── sandbox/          # 沙箱服务（Ubuntu + Chrome + VNC）
├── docker-compose.yml
├── .env              # 环境变量配置（需自行创建）
└── README.md
```

## 快速部署

### 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0

### 一键部署

1. **配置环境变量**

   项目根目录下的 `.env` 文件包含所有配置项，请根据实际情况修改：

   ```bash
   # 必须修改的配置
   COS_SECRET_ID=your_cos_secret_id_here       # 腾讯云 COS SecretId
   COS_SECRET_KEY=your_cos_secret_key_here     # 腾讯云 COS SecretKey
   COS_BUCKET=your_cos_bucket_here             # COS 存储桶名称

   # 可选修改
   POSTGRES_PASSWORD=postgres                   # 数据库密码
   UI_PORT=3000                                 # 前端端口
   API_PORT=8000                                # 后端端口
   SANDBOX_PORT=8080                            # 沙箱端口（调试/排查可用）
   ```

2. **配置 AI 模型**

   修改 `api/config.yaml` 中的 LLM 配置：

   ```yaml
   llm_config:
     base_url: https://api.deepseek.com/
     api_key: your_api_key_here
    model_name: deepseek-v4-flash
   ```

3. **启动所有服务**

   ```bash
   docker compose up -d --build
   ```

4. **访问系统**

   打开浏览器访问 `http://localhost:3000`（或按 `.env` 的 `UI_PORT` 调整端口）

### 服务架构

```
       ┌─────────────┐        API调用         ┌─────────────┐
       │  Next.js UI │ ─────────────────────► │   FastAPI   │
       │  (Port 3000)│   http://localhost:8000/api (CORS)   │
       └─────────────┘                        └──────┬──────┘
                                                     │
                                  ┌──────────────────┼──────────────────┐
                                  │                  │                  │
                                  ▼                  ▼                  ▼
                           ┌───────────┐      ┌───────────┐      ┌───────────┐
                           │ PostgreSQL│      │   Redis   │      │  Sandbox  │
                           │(Port 5432)│      │(Port 6379)│      │ (Port 8080)│
                           └───────────┘      └───────────┘      └───────────┘
```

### 容器列表

| 容器名称 | 服务 | 说明 |
|---------|------|------|
| multigen-ui | Next.js | 前端 UI 服务（对外端口 `3000`） |
| multigen-api | FastAPI | 后端 API 服务（对外端口 `8000`） |
| multigen-postgres | PostgreSQL | 数据库 |
| multigen-redis | Redis | 缓存 |
| multigen-sandbox | Sandbox | 沙箱环境（对外端口 `8080`） |

### 常用命令

```bash
# 启动所有服务（后台运行）
docker compose up -d --build

# 查看所有服务状态
docker compose ps

# 查看服务日志
docker compose logs -f              # 所有服务
docker compose logs -f multigen-api # 仅 API 服务
docker compose logs -f multigen-ui  # 仅 UI 服务

# 重启单个服务
docker compose restart multigen-api

# 停止所有服务
docker compose down

# 停止并清除数据卷（谨慎操作）
docker compose down -v
```

### 本地直连说明（无 Nginx）

- UI：`http://localhost:${UI_PORT:-3000}`
- API：`http://localhost:${API_PORT:-8000}/api/status`
- Sandbox：`http://localhost:${SANDBOX_PORT:-8080}`

## 本地开发

各子项目的本地开发说明请参考对应目录下的 README：

- [API 服务](./api/README.md)
- [前端 UI](./ui/README.md)
- [沙箱服务](./sandbox/README.md)

## License

[MIT](./LICENSE)
