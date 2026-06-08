# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MRKTGURU is an AI agent that edits **existing** websites over SSH. The user connects a server, the agent discovers sites on it, the user describes a task in Russian, and the agent triages the request, estimates a credit cost, then executes the edits over SSH with backup/rollback.

Stack: **FastAPI** backend + **Celery** workers + **Next.js 14** (App Router) frontend, on **PostgreSQL 16 (pgvector)** and **Redis**. The whole system runs in Docker Compose.

> The product was formerly "SiteDoc" and once included an app-builder ("AppForge") — both are gone. Ignore those names if you find them in old comments. The previous version of this file (the original product spec) is in git history: `git show HEAD~1:CLAUDE.md`.

## Commands

- **Whole stack:** `docker-compose up` from the repo root. Requires a `.env` (copy from `.env.example`). Services: `postgres` (pgvector/pgvector:pg16), `redis`, `backend`, `worker`, `beat`, `frontend`.
- **Ports:** backend → `localhost:8010` (container 8000); frontend → `localhost:3010` (container 3000).
- **Migrations:** run automatically on backend start (`alembic upgrade head && uvicorn ... --reload`). Manual: `docker compose exec backend alembic upgrade head`. New migration: `docker compose exec backend alembic revision -m "msg"` (versions in `backend/alembic/versions/`, currently through `0014`).
- **Worker / beat:** already wired as compose services. Manual: `celery -A app.tasks.celery_app.celery_app worker --loglevel=info` and `... beat ...`.
- **Frontend standalone:** `cd frontend && npm install && npm run dev` (3000) · `npm run build` (standalone output) · `npm run lint`.
- **Tests/lint:** the backend has **no test runner and no linter configured** (no pytest/ruff/black) — don't go hunting for one. The frontend has only Next's built-in `npm run lint`.
- **Deploy (prod):** push to `main`, then on the server at `82.26.152.59:/mrktguru_agent` run `git pull && docker compose restart <service>` (the live deploy flow this repo uses).

## Architecture — a task's lifecycle

One user task flows through these hops; each names the file that owns that step:

1. **Triage** — `app/services/agent/triage.py`: two-level Haiku classification (intent `action|fix|info|ops|control|reject` → task_type `tweak|feature|integration|…`).
2. **Estimate** — `app/services/agent/task_estimator.py`: parses the TZ, builds site context, injects the matching **workflow hint** + **solution-reuse context**, returns subtasks + a credit estimate.
3. **Approve / reserve** — `app/services/billing/budget.py` (`BudgetGuard`) reserves credits against the user's balance.
4. **Execute** — Celery `app.tasks.execute.run` → `app/services/agent/task_executor.py`: SSH connect, backup, read/edit files, run commands (gated by `command_policy.py`), self-verify with headless Playwright (`app/services/verify/headless.py`).
5. **Settle** — `app/services/billing/settlement.py`: idempotent charge keyed on `task.settled_at`; writes `token_transactions`.
6. **Post-task (fire-and-forget)** — `app.tasks.upsell` (suggestions) + `app.tasks.index_solution` (index the task into the reuse base).

## Cross-cutting systems

- **LLM layer registry** — `app/services/llm/registry.py`. One `resolve(layer_key)` call returns a model tier + system prompt + max_tokens for each of ~20 layers. Code defaults (`LAYER_DEFAULTS`) are overridable per-layer via the `llm_layers` DB table (admin UI). `seed_layers()` runs in `main.py` lifespan and auto-migrates stale model IDs. Models are Claude 4.x: Haiku 4.5 (cheap classification), Sonnet 4.6 (default), Opus 4.8 (heavy). Prompts live in `app/services/claude/prompts.py` (Russian, ~1000 lines).
- **Claude client** — `app/services/claude/client.py`: enforces **prompt caching** (`cache_control: ephemeral`) on system/context blocks; `run_agent()` drives tool-use loops; has an adaptive-thinking fallback. Keep system/context blocks cache-stable; put per-request content in the user message.
- **Workflows** — `app/services/claude/workflows/`: 57 `WorkflowDef`s across `sites/ bots/ backend_api/ integrations/ data/ devops/ mobile/ ai/ russian/`. Each = questionnaire + phases + credit bounds + upsell. `_types.py` holds the dataclass + `REGISTRY`; `__init__.py` exposes `get_workflow`, `build_workflow_hint`, `build_spec_hint`.
- **Solution reuse (pgvector)** — `app/services/solutions/`: `seeder.py` seeds all 57 workflows as `curated_skill` rows on startup; `indexer.py` indexes completed best-practice tasks; `checker.py` runs L1 (deterministic) → L2 (Haiku delta) → L3 (`APPLY|ADAPT|REFERENCE|GENERATE`); `dispatcher.py` activates skills by type/keyword; `embed.py` uses OpenAI `text-embedding-3-small` and **gracefully falls back to quality-ranking when `OPENAI_API_KEY` is absent**; `db.py` does vector search via raw `<=>` cosine SQL.
- **Billing** — two-phase: estimate → reserve → settle. `settlement.py`, `budget.py`, `pricing.py` (token→credit), `analytics.py`.
- **SSH** — `app/services/ssh/client.py` (Paramiko; password or private key; streaming exec + SFTP), `backup.py` (tar+gzip before edits; daily Celery-beat cleanup), `scanner.py` (server probe on registration).

## Conventions & gotchas

- **Async vs sync DB sessions** — `app/core/database.py`: FastAPI endpoints use `AsyncSessionLocal` (`+asyncpg`); Celery workers, Alembic, and the whole `solutions/` service use `SyncSessionLocal` (`+psycopg2`). Use the one that matches your side.
- **Idempotency over retries** — Celery tasks set `max_retries=0`. Recovery relies on idempotent settlement (`settled_at`) and resumable `task.agent_state` (JSONB), not auto-retry.
- **Frontend auth is client-side only** — JWT in `localStorage.token`, injected by an Axios interceptor in `frontend/lib/api.ts`. No server middleware guard; pages are `"use client"` and redirect themselves. WebSocket task logs connect to `${NEXT_PUBLIC_WS_URL}/ws/tasks/{taskId}?token=…` with message types `log` / `task_complete` / `task_paused`.
- **Frontend design tokens** — use the semantic Tailwind colors from `frontend/tailwind.config.ts` (`accent`, `surface`/`surface-2`/`surface-3`, `border`, `text-main`/`text-sub`/`text-muted`), not raw hex. On pages using `useSearchParams`, avoid fallback-less `<Suspense>` wrappers — that caused the login hydration bug.
- **Key env vars** — backend: `ANTHROPIC_API_KEY` (required), `FERNET_KEY` (credential encryption), `SECRET_KEY` (JWT), `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY` (optional → enables vector search), `FRONTEND_URL` (CORS). Frontend: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`.
- **Models** — `app/models/`: `user`, `site`, `server`, `task`, `task_log`, `solution` (+ `Pattern`, `ReuseLog`), `token_transaction`, `llm_layer`. `task` is the central record — `subtasks`, `triage`, `agent_state`, `spec`, and `upsell` are all JSONB columns on it.
