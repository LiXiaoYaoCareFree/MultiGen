# MultiGen 前端 UI

基于 Next.js 构建的前端用户界面，提供会话管理、AI 对话、远程桌面（VNC）等交互功能。

## 技术栈

- Next.js 16 (React 19)
- TypeScript
- Tailwind CSS 4
- Radix UI (组件库)
- noVNC (远程桌面)

## 项目结构

```
ui/
├── src/
│   ├── app/               # 页面路由
│   │   ├── page.tsx       # 首页
│   │   └── sessions/      # 会话页面
│   ├── components/        # 组件
│   │   ├── ui/            # 基础 UI 组件
│   │   └── tool-use/      # 工具使用相关组件
│   ├── lib/
│   │   └── api/           # API 客户端
│   ├── hooks/             # 自定义 Hooks
│   └── providers/         # Context Providers
├── public/                # 静态资源
├── next.config.ts         # Next.js 配置
├── Dockerfile
├── package.json
└── tsconfig.json
```

## API 调用

项目通过环境变量 `NEXT_PUBLIC_API_BASE_URL` 配置 API 地址：

- **开发环境**：默认 `http://localhost:8000/api`（直连 API 服务）
- **生产环境**：构建时设置为 `/api`（通过 Nginx 反向代理）

管理员登录控制相关环境变量：

- `NEXT_PUBLIC_ADMIN_LOGIN_REQUIRED`：是否启用管理员登录（`true`/`false`，默认 `false`）
- `NEXT_PUBLIC_ADMIN_PASSWORD`：管理员登录密码（仅在启用登录时生效）

## 本地开发

### 环境准备

- Node.js >= 22
- npm >= 10

可选管理员配置（在 `ui/.env.local` 中设置）：

- `NEXT_PUBLIC_ADMIN_LOGIN_REQUIRED=true`
- `NEXT_PUBLIC_ADMIN_PASSWORD=你的管理员密钥`

### 安装与启动

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

开发服务器默认运行在 `http://localhost:3000`，API 请求自动转发到 `http://localhost:8000/api`。

### 构建

```bash
npm run build
npm run start
```

## Docker 部署

UI 服务通过根目录的 `docker-compose.yml` 统一部署。Dockerfile 采用多阶段构建：

1. **deps** - 安装 npm 依赖
2. **builder** - 构建 Next.js 应用（standalone 模式）
3. **runner** - 最小化生产镜像

构建时通过以下参数注入前端配置：

- `NEXT_PUBLIC_API_BASE_URL=/api`
- `NEXT_PUBLIC_ADMIN_LOGIN_REQUIRED=false`
- `NEXT_PUBLIC_ADMIN_PASSWORD=`
