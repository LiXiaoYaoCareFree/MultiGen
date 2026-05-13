<div align="center">

# 🚀 MultiGen

### **A General-Purpose AI Agent System for Fully Private Deployment**

*Planner + ReAct multi-agent architecture · A2A & MCP native · Sandboxed execution · One-command deploy*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/)

**English** · [简体中文](./README.zh-CN.md)

<p align="center">
  <img src="assets/home%20page.png" alt="MultiGen Home Page" width="92%" />
</p>

</div>

---

## ✨ What is MultiGen?

**MultiGen** is an open-source, general-purpose AI Agent platform designed for **fully private, on-premise deployment**. It pairs a **Planner agent** (decomposes user goals into steps) with a **ReAct agent** (executes each step using tools), and runs every action inside an **isolated Docker sandbox** — so your data never leaves your infrastructure.

Out of the box, MultiGen can browse the web, run shell commands, generate images / videos / 3D models / TTS audio, build slide decks and reports, and orchestrate other agents via **A2A** and external tools via **MCP**.

> 💡 **Think of it as your private, self-hosted alternative to Manus / Claude Agent / GPT Agent — but you own the data, the model, and the stack.**

---

## 🎯 Key Features

| | |
|---|---|
| 🧠 **Planner + ReAct architecture** | A two-stage agent: the Planner breaks down the goal into JSON sub-steps, the ReAct agent iteratively reasons & acts on each step. |
| 🔌 **MCP & A2A native** | Plug in any MCP server (search, maps, code, custom tools) and delegate sub-tasks to peer agents via Agent-to-Agent protocol. |
| 🛡️ **Sandboxed execution** | Every shell / browser / file action runs inside an isolated Ubuntu + Chrome + VNC container. The model can't touch your host. |
| 🎨 **Multimodal generation** | Built-in tools for image (Volcengine / SD), video, 3D models, TTS (Qwen / podcasts), virtual anchors, audio mixing, slide decks. |
| 🌐 **Any OpenAI-compatible LLM** | Works with DeepSeek, Volcengine, SiliconFlow, Qwen, OpenAI, vLLM, Ollama, etc. — just edit `config.yaml`. |
| 🚢 **One-command deploy** | `docker compose up -d --build` brings up the full stack: UI, API, sandbox, Postgres, Redis, Nginx. |
| 📡 **Real-time streaming UI** | SSE-driven Next.js frontend renders plans, tool calls, intermediate results, and final answers live. |
| 🔁 **Replayable sessions** | Full session state in PostgreSQL; generated files mirrored locally and to Tencent COS for replay & sharing. |

---

## 📸 Showcase

### 🌐 Web Search & Knowledge Retrieval

<p align="center">
  <img src="assets/bings-search.png" alt="Web search workflow" width="92%" />
  <br/>
  <em>Agent plans the search, calls the right tool, and synthesizes a sourced answer.</em>
</p>

<p align="center">
  <img src="assets/bings-search-image.png" alt="Image search" width="92%" />
  <br/>
  <em>Image search and ranking, with live previews streamed back to the UI.</em>
</p>

### ⚙️ Settings & Configuration

<table width="100%">
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="assets/settings-1.png" alt="LLM provider settings" width="100%" />
      <br/><sub><b>LLM provider</b> — connect any OpenAI-compatible endpoint</sub>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="assets/settings-2.png" alt="Agent settings" width="100%" />
      <br/><sub><b>Agent behavior</b> — iterations, retries, search depth</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="assets/settings-3.png" alt="MCP server settings" width="100%" />
      <br/><sub><b>MCP servers</b> — plug in external tools live</sub>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="assets/settings-4.png" alt="A2A settings" width="100%" />
      <br/><sub><b>A2A agents</b> — federate with peer agents</sub>
    </td>
  </tr>
</table>

### 🖼️ Multimodal Generation

<p align="center">
  <img src="assets/img.png" alt="Generation workflow" width="92%" />
  <br/>
  <em>End-to-end creative workflow — from prompt, to plan, to rendered assets.</em>
</p>

<table>
  <tr>
    <td width="33%" align="center">
      <img src="assets/古风女子图1.jpg" width="100%" />
      <br/><sub>Generated portrait #1</sub>
    </td>
    <td width="33%" align="center">
      <img src="assets/古风女子图2.jpg" width="100%" />
      <br/><sub>Generated portrait #2</sub>
    </td>
    <td width="33%" align="center">
      <img src="assets/古风女子图5.jpeg" width="100%" />
      <br/><sub>Generated portrait #3</sub>
    </td>
  </tr>
</table>

### 🎙️ Podcasts & TTS

<p align="center">
  <img src="assets/tts_播客.png" alt="TTS Podcast generation" width="92%" />
  <br/>
  <em>Generate full multi-speaker podcasts with Qwen-TTS, automatically mixed with background music.</em>
</p>

---

## 🏗️ Architecture

```
              ┌─────────────────────────────────────────────┐
              │              Next.js UI  (3000)             │
              │   Plans · Steps · Tool calls · SSE stream   │
              └────────────────────┬────────────────────────┘
                                   │  /api  (SSE)
                                   ▼
              ┌─────────────────────────────────────────────┐
              │              FastAPI  (8000)                │
              │  ┌──────────────┐    ┌───────────────────┐  │
              │  │ AgentService │ →  │ AgentTaskRunner   │  │
              │  └──────────────┘    └────────┬──────────┘  │
              │                               ▼              │
              │              ┌────────────────────────────┐  │
              │              │   PlannerReAct Flow        │  │
              │              │  Planner ─► ReAct (loop)   │  │
              │              └─────┬──────────────────────┘  │
              │                    │ tools                   │
              │  ┌─────────────────┴──────────────────────┐  │
              │  │ file · shell · browser · search · MCP  │  │
              │  │ image · video · 3D · TTS · A2A · ...   │  │
              │  └────────────────────────────────────────┘  │
              └─────┬─────────────┬───────────────────┬─────┘
                    ▼             ▼                   ▼
              ┌──────────┐  ┌──────────┐     ┌──────────────────┐
              │PostgreSQL│  │  Redis   │     │  Docker Sandbox  │
              │ sessions │  │ streams  │     │  Ubuntu + Chrome │
              └──────────┘  └──────────┘     │     + VNC (8080) │
                                             └──────────────────┘
```

**Agent execution flow:**
1. `AgentService` receives a chat message → dispatches it to an `AgentTaskRunner` via Redis Streams.
2. `AgentTaskRunner` runs `PlannerReActFlow`:
   - **PlannerAgent** — decomposes the request into a JSON plan of sub-steps.
   - **ReActAgent** — for each step, iteratively reasons → calls a tool → observes → continues, then summarizes.
3. Events stream back via SSE (`plan` · `title` · `step` · `message` · `tool` · `wait` · `error` · `done`).

---

## 🚀 Quick Start

### Prerequisites

- 🐳 Docker `>= 20.10`
- 🐙 Docker Compose `>= 2.0`
- 🔑 An API key for any OpenAI-compatible LLM (DeepSeek / Volcengine / OpenAI / vLLM / Ollama…)

### 1. Clone

```bash
git clone https://github.com/your-org/multigen.git
cd multigen
```

### 2. Configure environment

Create a `.env` file in the project root:

```bash
# ── Required ─────────────────────────────────────────────
COS_SECRET_ID=your_cos_secret_id_here       # Tencent COS SecretId
COS_SECRET_KEY=your_cos_secret_key_here     # Tencent COS SecretKey
COS_BUCKET=your_cos_bucket_here             # COS bucket name
OPENAI_API_KEY=your_llm_api_key_here        # LLM API key

# ── Optional ─────────────────────────────────────────────
NGINX_PORT=8088                             # public port
ADMIN_API_KEY=your_admin_api_key_here       # admin auth key
LLM_PROVIDER=volcano                        # deepseek / openai / volcano
TENCENT_AI3D_API_KEY=...                    # for 3D model generation
DASHSCOPE_API_KEY=...                       # for Qwen-TTS
```

### 3. Configure the LLM

Edit `api/config.yaml`:

```yaml
llm_config:
  base_url: https://api.deepseek.com/
  api_key: YOUR_DEEPSEEK_API_KEY
  model_name: deepseek-reasoner
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
      url: https://mcp.amap.com/mcp?key=YOUR_AMAP_API_KEY
    jina-mcp-server:
      transport: streamable_http
      enabled: true
      url: https://mcp.jina.ai/v1
      headers:
        Authorization: Bearer YOUR_JINA_API_KEY
```

### 4. Launch

```bash
docker compose up -d --build
```

### 5. Open

Visit **`http://localhost:8088`** (or whichever `NGINX_PORT` you set). The API health probe lives at `/api/status`.

---

## 🧩 Built-in Tools

| Tool | Purpose |
|---|---|
| `file` | Read / write / patch files inside the sandbox |
| `shell` | Run shell commands in the sandbox |
| `browser` | Headless Chrome — navigate, click, extract, screenshot |
| `search` | Web search (Bing / Google / Jina) |
| `message` | Ask the user a clarifying question mid-task |
| `image_generation` · `volcano_image` | Text-to-image generation |
| `volcano_video` · `video_concatenation` | Text-to-video & post-processing |
| `model_3d` | Text/image-to-3D via Tencent AI3D |
| `virtual_anchor` | Avatar / digital-human video |
| `qwen_tts` · `audio_mixing` | TTS + multi-track audio mixing |
| `mcp` | Call any registered MCP server |
| `a2a` | Delegate a sub-task to a peer agent |

> 📚 To add your own tool, see **[CLAUDE.md → Adding a New Tool](./CLAUDE.md#adding-a-new-tool)**.

---

## 📦 Project Layout

```
MultiGen/
├── api/              # Backend API service (FastAPI)
│   ├── app/          # Domain / application / infrastructure layers
│   ├── tests/        # Pytest suite
│   └── config.yaml   # Runtime LLM / MCP / A2A config
├── ui/               # Frontend (Next.js 14, App Router)
├── sandbox/          # Sandbox runtime (Ubuntu + Chrome + VNC)
├── nginx/            # Reverse-proxy gateway
│   ├── nginx.conf
│   └── conf.d/default.conf
├── assets/           # Screenshots used in this README
├── docker-compose.yml
├── .env              # Environment variables (create your own)
└── README.md
```

---

## 🐳 Container Reference

| Container | Service | Description |
|---|---|---|
| `manus-nginx` | Nginx | Reverse-proxy gateway, the only exposed entrypoint |
| `manus-ui` | Next.js | Frontend UI |
| `manus-api` | FastAPI | Backend API |
| `manus-postgres` | PostgreSQL | Session & message store |
| `manus-redis` | Redis | Task streams & cache |
| `manus-sandbox` | Sandbox | Ubuntu + Chrome + VNC isolated runtime |

---

## 🛠️ Common Commands

```bash
# Start everything (detached) + rebuild images
docker compose up -d --build

# Check service status
docker compose ps

# Follow logs
docker compose logs -f
docker compose logs -f manus-api
docker compose logs -f manus-ui

# Restart a single service
docker compose restart manus-api

# Stop everything
docker compose down

# Stop and wipe data volumes (DANGEROUS — deletes the database)
docker compose down -v
```

---

## 🔒 Enable HTTPS

1. Place your TLS files in `nginx/ssl/`:
   - `fullchain.pem`
   - `privkey.pem`
2. In `nginx/conf.d/default.conf`, add/enable a `listen 443 ssl` server block pointing at those files.
3. In `docker-compose.yml`, enable the `443:443` port mapping (and mount `nginx/ssl` if needed).
4. Apply changes:
   ```bash
   docker compose restart manus-nginx
   ```

---

## 💻 Local Development

Each sub-project has its own dev guide:

- 🔧 [API service](./api/README.md) — FastAPI, SQLAlchemy async, Alembic, Pytest
- 🎨 [UI service](./ui/README.md) — Next.js 14, App Router, SSE streaming
- 📦 [Sandbox service](./sandbox/README.md) — Ubuntu + Chrome + VNC runtime

Quickstart for the API:

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -r requirements.txt
playwright install
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🗺️ Roadmap

- [x] Planner + ReAct dual-agent flow
- [x] MCP & A2A integrations
- [x] Multimodal tools (image / video / 3D / TTS)
- [x] DeepSeek reasoning-model (v4) compatibility
- [ ] Long-term memory / RAG plugin
- [ ] Multi-user workspace permissions
- [ ] Plugin marketplace for tools & MCP servers
- [ ] Mobile-friendly UI

---

## 🤝 Contributing

Contributions are warmly welcomed — issues, PRs, tool plugins, and translations alike.

1. Fork the repository
2. Create your feature branch (`git checkout -b feat/amazing-thing`)
3. Commit your changes (`git commit -m 'feat: add amazing thing'`)
4. Push to the branch (`git push origin feat/amazing-thing`)
5. Open a Pull Request

Please read [CLAUDE.md](./CLAUDE.md) first — it documents the architecture, the agent contracts, and how to add new tools / LLM providers safely.

---

## 🙏 Acknowledgements

MultiGen stands on the shoulders of these excellent projects:

- [FastAPI](https://fastapi.tiangolo.com/) · [Next.js](https://nextjs.org/) · [SQLAlchemy](https://www.sqlalchemy.org/)
- [Model Context Protocol](https://modelcontextprotocol.io/) · [A2A](https://google.github.io/A2A/)
- [Playwright](https://playwright.dev/) · [Docker](https://www.docker.com/)
- DeepSeek · Volcengine · SiliconFlow · Qwen — for outstanding open-source LLM endpoints

---

## 📄 License

Released under the [MIT License](./LICENSE).

<div align="center">

**If MultiGen is useful to you, please consider giving it a ⭐ — it really helps!**

Made with ❤️ for builders of private AI agents.

</div>
