English | [中文](./README.zh-CN.md)

# MultiGen - General-Purpose AI Agent System

MultiGen is a general-purpose AI Agent system designed for fully private deployments. It connects Agents/Tools via A2A + MCP, and supports running built-in tools and operations inside a sandbox.

## Screenshots

<p align="center">
  <img src="assets/home%20page.png" alt="Home page" width="92%" />
</p>

<table width="100%">
  <tr>
    <td width="50%" align="center">
      <img src="assets/bings-search.png" alt="Bing search" width="95%" />
    </td>
    <td width="50%" align="center">
      <img src="assets/bings-search-image.png" alt="Bing image search" width="95%" />
    </td>
  </tr>
</table>

<table width="100%">
  <tr>
    <td width="50%" align="left" valign="top">
      <img src="assets/settings-1.png" alt="Settings 1" width="95%" />
    </td>
    <td width="50%" align="right" valign="top">
      <img src="assets/settings-2.png" alt="Settings 2" width="95%" />
    </td>
  </tr>
  <tr>
    <td width="50%" align="left" valign="bottom">
      <img src="assets/settings-3.png" alt="Settings 3" width="95%" />
    </td>
    <td width="50%" align="right" valign="bottom">
      <img src="assets/settings-4.png" alt="Settings 4" width="95%" />
    </td>
  </tr>
</table>

## Project Layout

```
mooc-manus/
├── api/              # Backend API service (FastAPI)
├── ui/               # Frontend service (Next.js)
├── sandbox/          # Sandbox service (Ubuntu + Chrome + VNC)
├── docker-compose.yml
├── .env              # Environment variables (create it yourself)
└── README.md
```

## Quick Start (Local Deployment)

### Prerequisites

- Docker >= 20.10
- Docker Compose >= 2.0

### One-command Deployment

1. **Configure environment variables**

   Create a `.env` file in the project root and adjust values as needed:

   ```bash
   # Required
   COS_SECRET_ID=your_cos_secret_id_here       # Tencent COS SecretId
   COS_SECRET_KEY=your_cos_secret_key_here     # Tencent COS SecretKey
   COS_BUCKET=your_cos_bucket_here             # COS bucket name
   OPENAI_API_KEY=your_vocano_api_key_here     # Vocano API key
 

   # Optional
   UI_PORT=3000                                # Web UI port
   API_PORT=8000                               # Backend API port
   SANDBOX_PORT=8080                           # Sandbox port (debugging)
   ADMIN_API_KEY=your_admin_api_key_here       # Admin API key for authentication
   LLM_PROVIDER=vocano                      # LLM provider (deepseek or openai)
   TENCENT_AI3D_API_KEY=your_tencent_ai3d_api_key_here # Tencent AI3D API key
   DASHSCOPE_API_KEY=your_dashscope_api_key_here # Dashscope API key
   ```

2. **Configure the AI model**

   Update the LLM configuration in `api/config.yaml`:

  ```yaml
  llm_config:
    base_url: https://api.deepseek.com/
    api_key: YOUR_DEEPSEEK_API_KEY
    model_name: deepseek-v4-flash
    temperature: 0.7
    max_tokens: 8192
  agent_config:
    max_iterations: 100
    max_retries: 3
    max_search_results: 10
  mcp_config:
    mcpServers:
      amap-maps-streamableHTTP:
        transport: streamable_http
        enabled: true
        description: null
        env: null
        command: null
        args: null
        url: https://mcp.amap.com/mcp?key=YOUR_AMAP_API_KEY
        headers: null
      jina-mcp-server:
        transport: streamable_http
        enabled: true
        description: null
        env: null
        command: null
        args: null
        url: https://mcp.jina.ai/v1
        headers:
          Authorization: Bearer YOUR_JINA_API_KEY
  ```

3. **Start all services**

   ```bash
   docker compose up -d --build
   ```

4. **Open the app**

   Visit `http://localhost:3000` (or the port defined by `UI_PORT` in `.env`).

### Local URLs

- Web UI: `http://localhost:${UI_PORT:-3000}`
- API health check: `http://localhost:${API_PORT:-8000}/api/status`
- Sandbox: `http://localhost:${SANDBOX_PORT:-8080}`

## Architecture

```
       ┌─────────────┐         API call         ┌─────────────┐
       │  Next.js UI │ ───────────────────────► │   FastAPI   │
       │  (Port 3000)│   http://localhost:8000/api (CORS)     │
       └─────────────┘                         └──────┬──────┘
                                                      │
                                   ┌──────────────────┼──────────────────┐
                                   │                  │                  │
                                   ▼                  ▼                  ▼
                            ┌───────────┐      ┌───────────┐      ┌───────────┐
                            │ PostgreSQL│      │   Redis   │      │  Sandbox  │
                            │(Port 5432)│      │(Port 6379)│      │(Port 8080)│
                            └───────────┘      └───────────┘      └───────────┘
```

## Containers

| Container | Service | Description |
|---------|------|------|
| multigen-ui | Next.js | Frontend UI service (exposed on `3000`) |
| multigen-api | FastAPI | Backend API service (exposed on `8000`) |
| multigen-postgres | PostgreSQL | Database |
| multigen-redis | Redis | Cache |
| multigen-sandbox | Sandbox | Sandbox runtime (exposed on `8080`) |

## Common Commands

```bash
# Start everything (detached) and build images
docker compose up -d --build

# Check status
docker compose ps

# Follow logs
docker compose logs -f
docker compose logs -f multigen-api
docker compose logs -f multigen-ui

# Restart a single service
docker compose restart multigen-api

# Stop everything
docker compose down

# Stop and remove volumes (dangerous)
docker compose down -v
```

## Local Direct Access (No Nginx)

- Web UI: `http://localhost:${UI_PORT:-3000}`
- API: `http://localhost:${API_PORT:-8000}/api/status`
- Sandbox: `http://localhost:${SANDBOX_PORT:-8080}`

## Local Development

See the READMEs inside each sub-project:

- [API](./api/README.md)
- [UI](./ui/README.md)
- [Sandbox](./sandbox/README.md)

## License

[MIT](./LICENSE)
