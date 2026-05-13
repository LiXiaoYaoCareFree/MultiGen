# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MultiGen is a general-purpose AI Agent system for fully private deployments. It uses a **Planner + ReAct** multi-agent architecture with A2A (Agent-to-Agent) and MCP (Model Context Protocol) tool connectivity, and executes operations inside an isolated Docker sandbox.

## Architecture

```
Next.js UI (3000) → FastAPI API (8000) → PostgreSQL / Redis / Tencent COS
                                        ↓
                               Docker Sandbox (8080)
                               Ubuntu + Chrome + VNC
```

**Agent execution flow:**
1. `AgentService` (application layer) receives a chat message and dispatches it to an `AgentTaskRunner` via a Redis Stream task queue.
2. `AgentTaskRunner` runs `PlannerReActFlow`, which coordinates two agents:
   - `PlannerAgent` — breaks the user request into sub-steps (JSON output, no tool calls)
   - `ReActAgent` — iteratively executes each step using tools, then summarizes
3. Events are streamed back to the frontend via SSE (`/api/sessions/{id}/chat`).

**Event types** (discriminated union in `app/domain/models/event.py`): `plan`, `title`, `step`, `message`, `tool`, `wait`, `error`, `done`.

**Tools available to agents** (`app/domain/services/tools/`): `file`, `shell`, `browser`, `search`, `message` (ask_user), `image_generation`, `volcano_image`, `volcano_video`, `video_concatenation`, `model_3d`, `virtual_anchor`, `qwen_tts`, `audio_mixing`, `mcp`, `a2a`.

**LLM abstraction:** `app/domain/external/llm.py` defines a `Protocol`. The only implementation is `OpenAILLM` (`app/infrastructure/external/llm/openai_llm.py`), which supports any OpenAI-compatible endpoint (DeepSeek, Volcengine, SiliconFlow, etc.).

**DeepSeek thinking models:** Models whose names start with `deepseek-v4` are treated as reasoning models. When tool calls are present in a turn, `reasoning_content` **must** be included in subsequent history; when there are no tool calls, it is passthrough-safe. The codebase handles both cases with a compatibility guard in `BaseAgent`.

**Storage:** Files are stored in Tencent Cloud COS. The `dialogue/<session_id>/` directory mirrors sandbox-generated files locally for replay. Session state is in PostgreSQL via SQLAlchemy async + Alembic migrations.

**Configuration:** Runtime config is split:
- `.env` / environment variables → `core/config.py` (Settings via pydantic-settings); used for infra (DB, Redis, COS, sandbox).
- `api/config.yaml` → loaded at request time by `FileAppConfigRepository`; contains LLM config, agent config, MCP servers, A2A agents.

## Development Commands

### Full stack (Docker)
```bash
docker compose up -d --build   # start everything
docker compose logs -f multigen-api
docker compose restart multigen-api
docker compose down
```

### API (local)
```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install uv && uv pip install -r requirements.txt
playwright install

# start dev server (hot reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# or
bash dev.sh

# run all tests
pytest

# run a single test file
pytest tests/test_deepseek_reasoning_content_guard.py -v

# database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

Local API requires PostgreSQL and Redis on `localhost`. Set in `.env`:
```
SQLALCHEMY_DATABASE_URI=postgresql+asyncpg://postgres:postgres@localhost:5432/manus
REDIS_HOST=localhost
SANDBOX_ADDRESS=          # empty = dynamic Docker sandbox creation
ADMIN_AUTH_REQUIRED=false
```

### UI (local)
```bash
cd ui
npm install
npm run dev        # http://localhost:3000
npm run build && npm run start
```

Requires `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api` (set in `ui/.env.local`).

### Sandbox (local dev)
```bash
cd sandbox/.devops
docker compose up -d
ssh root@localhost -p 2222   # password: root
# inside container:
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Key File Locations

| Concern | Path |
|---|---|
| App entrypoint | `api/app/main.py` |
| Settings | `api/core/config.py` |
| Runtime config (LLM/MCP/A2A) | `api/config.yaml` |
| Dependency wiring | `api/app/interfaces/service_dependencies.py` |
| Agent flow | `api/app/domain/services/flows/planner_react.py` |
| Task runner | `api/app/domain/services/agent_task_runner.py` |
| Base agent (memory, tool dispatch, context shrink) | `api/app/domain/services/agents/base.py` |
| LLM implementation | `api/app/infrastructure/external/llm/openai_llm.py` |
| Event model | `api/app/domain/models/event.py` |
| API routes | `api/app/interfaces/endpoints/routes.py` |
| Test fixtures | `api/tests/conftest.py` |

## Adding a New Tool

1. Create `api/app/domain/services/tools/<name>.py` inheriting `BaseTool`.
2. Register it in `PlannerReActFlow.__init__` tool list (`api/app/domain/services/flows/planner_react.py`).
3. Add a `ToolContent` variant in `event.py` if UI display is needed.
4. Handle the new `tool_name` in `AgentTaskRunner._handle_tool_event` for file sync or frontend enrichment.

## Adding a New LLM Provider

Implement the `LLM` protocol from `app/domain/external/llm.py` and wire it in `service_dependencies.get_agent_service()`. The `OpenAILLM` class already handles any OpenAI-compatible endpoint — typically only a new `config.yaml` entry is needed.
