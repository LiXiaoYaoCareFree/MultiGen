# MoocManus 沙箱服务

基于 Ubuntu 22.04 构建的沙箱环境，提供隔离的代码执行、浏览器自动化和远程桌面访问能力。

## 技术栈

- Ubuntu 22.04
- Python 3.10 + FastAPI
- Node.js 24 (LTS)
- Chromium (浏览器自动化)
- Xvfb + x11vnc + websockify (虚拟显示 + VNC)
- Supervisor (进程管理)

## 架构

沙箱通过 Supervisor 管理多个进程：

| 进程 | 端口 | 说明 |
|------|------|------|
| FastAPI | 8080 | REST API（文件操作、Shell 执行） |
| Chrome | 8222 (内部) | 浏览器实例 |
| socat | 9222 | Chrome DevTools Protocol 代理 |
| Xvfb | - | 虚拟显示器 (:1) |
| x11vnc | 5900 | VNC 服务 |
| websockify | 5901 | WebSocket VNC 代理 |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/file/read-file` | 读取文件 |
| POST | `/api/file/write-file` | 写入文件 |
| POST | `/api/file/upload-file` | 上传文件 |
| GET | `/api/file/download-file` | 下载文件 |
| POST | `/api/shell/exec-command` | 执行命令 |
| POST | `/api/shell/read-shell-output` | 读取 Shell 输出 |
| GET | `/api/supervisor/status` | 获取进程状态 |

## 本地开发

### 使用开发容器

```bash
cd .devops
docker compose up -d

# SSH 连接到开发容器
ssh root@localhost -p 2222
# 密码: root
```

### 启动服务

在容器内或本地：

```bash
# 安装依赖
pip3 install -r requirements.txt

# 启动 API 服务
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Docker 部署

沙箱服务通过根目录的 `docker-compose.yml` 统一部署。生产环境中沙箱作为固定容器运行，API 服务通过 `SANDBOX_ADDRESS=manus-sandbox` 连接。

### 端口说明

在 Docker Compose 部署中，沙箱端口仅在容器网络内部可访问，不对外暴露：

- `8080` - FastAPI REST API
- `9222` - Chrome DevTools Protocol
- `5900` - VNC RFB
- `5901` - WebSocket VNC（API 服务通过此端口代理 VNC 到前端）
