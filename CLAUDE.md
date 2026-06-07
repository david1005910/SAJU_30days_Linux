# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube automation pipeline for a Korean traditional astrology (사주명리학) channel. The system generates one episode per day from a 30-day curriculum using 100% deterministic Saju calculations fed into Claude AI for interpretation, Remotion for video rendering, and automated YouTube publishing.

## Monorepo Structure

pnpm workspaces with the following packages:

- `apps/web` — Next.js 14 operator dashboard (episode list, approval, cost tracking)
- `apps/worker` — BullMQ worker for 8-stage pipeline orchestration
- `apps/api` — lives under `services/api`, FastAPI backend for Saju calculation + Claude interpretation
- `packages/db` — Prisma schema, migrations, and seed scripts
- `packages/remotion` — React-based video composition and rendering

## Commands

### Infrastructure (must run first)
```bash
docker compose -f infra/docker-compose.yml up -d   # Start PostgreSQL + Redis
```

### Full system
```bash
./start.sh          # Start everything (infra + all services)
./stop.sh           # Stop everything
./test-pipeline.sh  # Run a full pipeline test (generates one episode)
```

### Development
```bash
pnpm install                    # Install JS dependencies
pnpm dev                        # Next.js dashboard + BullMQ worker (concurrent)
pnpm dev:web                    # Dashboard only (port 3000)
pnpm dev:worker                 # Worker only

# FastAPI backend (port 8000)
cd services/api && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Database
```bash
pnpm db:push                                      # Apply schema to local DB (no migration file)
pnpm db:migrate dev --name <name>                 # Create tracked migration
pnpm db:seed                                      # Load curriculum + sample data
pnpm db:studio                                    # Visual DB editor at localhost:5555
```

### Python (services/api)
```bash
cd services/api
uv pip install -e ".[dev]"   # Install with dev extras
uv run pytest                # Run tests
uv run black .               # Format
uv run ruff check .          # Lint
```

### Build
```bash
pnpm build                         # Build all JS workspaces
docker build -f Dockerfile.web .   # Build Next.js container
docker build -f Dockerfile.api .   # Build FastAPI container
```

## Architecture: 8-Stage Pipeline

```
주제 선정 → 사주 계산 → AI 해석 → 장면 분할 → 이미지 생성 → TTS → 자막 → 렌더/업로드
```

Jobs are managed by BullMQ (Redis-backed). Each stage reads episode state from PostgreSQL, appends results (assets, costs, errors) to derived tables, and never mutates input state. See `apps/worker/src/queues/pipeline.ts` for orchestration.

Episode state machine: `QUEUED → RUNNING → REVIEW → APPROVED → PUBLISHED`

## Critical Constraints

**Deterministic calculations:** Saju calculations use `services/api/saju/` (Python engine with `sxtwl` and `korean-lunar-calendar`), never AI. AI is only used to interpret already-calculated facts.

**Validation gate:** All Claude API output passes through `services/api/interpret/claude_client.py`'s `ValidationGate` before storage. It checks that AI output only references calculated Saju pillars, uses proper Korean, and avoids fear-mongering or medical claims. Never bypass this.

**Cost tracking:** Every external API call (Claude, image gen, TTS) must log to the `CostLog` Prisma table with `stage`, `item`, `quantity`, and `unitCost` fields.

**Korean locale hardcoded:** All TTS, date parsing, and formatting assumes `ko-KR` / `Asia/Seoul`. No generalization needed.

**BullMQ jobs are idempotent:** Jobs must be safe to retry. Use DB state as source of truth, not in-memory state.

## Key Environment Variables

Required in `.env`:
```
ANTHROPIC_API_KEY        # From console.anthropic.com
DATABASE_URL             # postgresql://saju:saju@localhost:5432/saju
REDIS_URL                # redis://localhost:6379
NEXTAUTH_SECRET          # 32+ char random string
JWT_SECRET               # JWT signing key
```

Optional (for YouTube):
```
YOUTUBE_CLIENT_SECRET_PATH   # Path to OAuth client_secret.json
YOUTUBE_CHANNEL_ID
```

## Service Ports

| Service | Port |
|---------|------|
| Next.js Dashboard | 3000 |
| FastAPI Backend | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Prisma Studio | 5555 |

## Debugging

- API docs (Swagger): http://localhost:8000/docs
- DB UI: `pnpm db:studio` → http://localhost:5555
- Container logs: `docker compose -f infra/docker-compose.yml logs -f`
- Redis CLI: `docker exec -it saju-redis redis-cli`
