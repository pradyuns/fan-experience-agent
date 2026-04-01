# Fan Experience Agent

Fan Experience Agent is an event-day concierge backend that turns a ticket-purchase webhook into a personalized pre-event dining plan. It enriches each purchase with venue context, dining candidates, timing feasibility, weather, and reservation options, then generates a structured itinerary through an asynchronous FastAPI + Celery pipeline.

The project is designed to demonstrate a production-style agentic backend with deterministic guardrails, background task orchestration, relational persistence, and a smoke-testable end-to-end recommendation flow.

## What It Does

- Accepts a purchase webhook after a fan buys event tickets
- Creates a planning workflow tied to the user, event, and purchase
- Enriches the request with event details, preferences, restaurant candidates, weather, and timing constraints
- Uses Anthropic to generate a structured dining plan
- Persists plan versions, confidence metadata, and notifications
- Supports reservation preview and reservation confirmation flows

## Architecture

### Core Components

- `FastAPI`
  Handles webhook ingestion, plan retrieval, user preference reads, and reservation endpoints.

- `Celery + Redis`
  Processes asynchronous plan generation outside the request/response path.

- `PostgreSQL`
  Stores users, events, purchases, plans, plan versions, reservations, notifications, and preference state.

- `Anthropic`
  Generates the final structured dining plan only after deterministic enrichment and constraint filtering, so model output is grounded in validated structured context rather than open-ended prompting.

### Runtime Flow

1. `POST /webhooks/purchase` receives a signed purchase payload.
2. The API creates a `Purchase` and a `Plan` in `GENERATING` state.
3. Celery picks up a background task to generate the plan.
4. The worker gathers tool context and calls Anthropic.
5. The resulting plan is validated, persisted as a `PlanVersion`, and the parent `Plan` becomes `ACTIVE`.
6. Clients can fetch the plan and run reservation preview / confirm flows.

Plan lifecycle: `GENERATING` -> `ACTIVE` -> `FAILED`

## Key Features

- Webhook-triggered itinerary generation
- Async background plan creation with Celery
- Structured plan persistence with version history
- Reservation preview and confirmation flow
- HMAC validation for purchase ingestion
- Live local smoke flow with Docker, Postgres, Redis, API, and worker
- GitHub Actions CI on PRs and pushes to `main`

## API Surface

### Webhooks

- `POST /webhooks/purchase`
  Accepts a signed ticket-purchase payload and queues plan generation.

### Plans

- `GET /plans/{plan_id}`
  Returns the plan, current version, and historical versions.

- `POST /plans/{plan_id}/refine`
  Accepts follow-up refinement input for a plan.

- `POST /plans/{plan_id}/feedback`
  Accepts user feedback on the generated plan.

### Reservations

- `POST /plans/{plan_id}/reservations/preview`
  Creates a reservation preview and returns an idempotency key.

- `POST /plans/{plan_id}/reservations/confirm`
  Confirms a previously previewed reservation.

### Users

- `GET /users/{user_id}/preferences`
  Returns stored preference signals for a user.

## Data Model

### Primary Entities

- `User`
  Represents the fan receiving the dining plan.

- `Event`
  Represents the ticketed event, venue, and timing context.

- `Purchase`
  Represents the source ticket purchase that triggers planning.

- `Plan`
  Represents the top-level planning workflow for a purchase.

- `PlanVersion`
  Stores immutable generated plan snapshots and confidence metadata.

- `Reservation`
  Stores previewed and confirmed dining reservations.

- `Notification`
  Stores user-facing plan and reservation notifications.

- `UserPreference`
  Stores learned or updated preference signals.

## Reliability Notes

- Purchase webhooks use HMAC verification
- Background processing is decoupled through Celery
- Reservation confirmation uses idempotency keys
- The system persists plan versions rather than mutating a single payload in place
- The live runtime path has been smoke-tested against a real Anthropic key

## Testing

The test suite covers:

- tool-layer behavior such as event lookup and arrival calculations
- agent-session parsing and guardrails
- service-layer persistence and state transitions
- webhook, plan, reservation, and user API endpoints
- background task behavior for plan generation and adaptation logic

The suite covers unit, API, and worker/integration tests across webhook ingestion, planning state transitions, reservation idempotency, plan adaptation flows, and observability wiring. Current local verification: `95` passing tests.

Run the full suite:

```bash
PYTHONPATH=src pytest tests/ -q --tb=short
```

## Environment Variables

The app loads environment variables from a local `.env` file in the repo root.

### Required

- `FAN_ANTHROPIC_API_KEY`

### Common Defaults

- `FAN_DATABASE_URL=postgresql+asyncpg://fan_experience:fan_experience@localhost:5432/fan_experience`
- `FAN_REDIS_URL=redis://localhost:6379/0`
- `FAN_WEBHOOK_HMAC_SECRET=dev-secret`

### Docker Compose Support

The same `.env` may also contain:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`

These are used by Docker Compose and are ignored by the Python settings layer.

## Local Development

### Prerequisites

- Python 3.12
- Docker

Install dependencies:

```bash
pip install -e ".[dev]"
```

Create a local `.env`:

```bash
cp .env.example .env
```

Set at least:

```env
FAN_ANTHROPIC_API_KEY=your_real_key_here
```

Optional Grafana credentials:

```env
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

## Start Local Infrastructure

```bash
docker compose up -d postgres redis otel-collector prometheus tempo grafana
```

Optional validation:

```bash
docker compose config
docker ps --filter name=fan-experience-postgres --filter name=fan-experience-redis --filter name=fan-experience-grafana
```

Local observability endpoints:

- OTLP HTTP ingest: `http://localhost:4318`
- Prometheus metrics from the collector: `http://localhost:9464/metrics`
- Prometheus UI: `http://localhost:9090`
- Tempo query API: `http://localhost:3200`
- Grafana UI: `http://localhost:3000`

Grafana ships pre-provisioned with:

- `Prometheus` datasource at `http://prometheus:9090`
- `Tempo` datasource at `http://tempo:3200`
- `Fan Experience Observability` dashboard in the `Observability` folder

Logs remain stdout-only in this repo. Grafana covers metrics and traces only in the current setup.

## Bootstrap the Database

Create tables:

```bash
PYTHONPATH=src python - <<'PY'
import asyncio
from fan_experience.db.engine import engine
from fan_experience.db.models import Base

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(main())
PY
```

Seed one local smoke-test user and event:

```bash
PYTHONPATH=src python - <<'PY'
import asyncio
import uuid
from datetime import datetime, timezone

from fan_experience.db.engine import async_session_factory
from fan_experience.db.models import Event, User

USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EVENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

async def main():
    async with async_session_factory() as session:
        if await session.get(User, USER_ID) is None:
            session.add(
                User(
                    id=USER_ID,
                    name="Smoke Test Fan",
                    email="smoke@example.com",
                    timezone="UTC",
                )
            )
        if await session.get(Event, EVENT_ID) is None:
            session.add(
                Event(
                    id=EVENT_ID,
                    name="Smoke Test Game",
                    venue_name="Test Arena",
                    venue_address="123 Test St",
                    venue_lat=29.4260,
                    venue_lng=-98.4861,
                    event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
                    doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
                    genre="basketball",
                )
            )
        await session.commit()

asyncio.run(main())
PY
```

## Run the System

Start the API:

```bash
PYTHONPATH=src uvicorn fan_experience.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, start the worker:

```bash
PYTHONPATH=src celery -A fan_experience.tasks.celery_app.celery_app worker -l info -P solo
```

Open Grafana at `http://localhost:3000` and sign in with the configured admin credentials to view:

- the `Fan Experience Observability` dashboard for metrics
- Grafana Explore with the `Tempo` datasource for traces

## Smoke Test

Send a signed purchase webhook:

```bash
PYTHONPATH=src python - <<'PY'
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

body = {
    "purchase_id": "smoke-purchase-001",
    "user_id": "11111111-1111-1111-1111-111111111111",
    "event_id": "22222222-2222-2222-2222-222222222222",
    "ticket_count": 2,
    "purchased_at": datetime.now(timezone.utc).isoformat(),
}
raw = json.dumps(body).encode()
signature = hmac.new(b"dev-secret", raw, hashlib.sha256).hexdigest()

response = httpx.post(
    "http://127.0.0.1:8000/webhooks/purchase",
    content=raw,
    headers={
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
    },
)

print(response.status_code)
print(response.text)
PY
```

Expected response shape:

```json
{"plan_id":"...","status":"generating"}
```

Fetch the generated plan:

```bash
curl http://127.0.0.1:8000/plans/<PLAN_ID>
```

Preview a reservation:

```bash
curl -X POST http://127.0.0.1:8000/plans/<PLAN_ID>/reservations/preview \
  -H "Content-Type: application/json" \
  -d '{
    "action": "book",
    "candidate_id": "rest-002",
    "dining_time": "2026-07-01T17:00:00Z",
    "party_size": 2
  }'
```

Confirm the reservation:

```bash
curl -X POST http://127.0.0.1:8000/plans/<PLAN_ID>/reservations/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "<IDEMPOTENCY_KEY_FROM_PREVIEW>"
  }'
```

After the smoke flow runs, verify observability:

```bash
curl -sf http://localhost:9090/-/ready
curl -sf http://localhost:3000/api/health
curl -sf http://localhost:9464/metrics | grep fan_http_requests_total
```

In Grafana:

- open the `Fan Experience Observability` dashboard and confirm panels populate
- open Explore, select the `Tempo` datasource, and search for the `fan-experience-agent` service
- inspect a trace that includes the HTTP request span and the propagated Celery task span

## Example Responses

### Purchase Webhook Response

```json
{
  "plan_id": "80076257-8faf-41e3-93e6-e0f85eaddd08",
  "status": "generating"
}
```

### Plan Response Shape

```json
{
  "id": "80076257-8faf-41e3-93e6-e0f85eaddd08",
  "status": "ACTIVE",
  "current_version": {
    "version_number": 1,
    "shortlist": [
      {
        "candidate_id": "rest-002",
        "recommended": true,
        "dining_time": "2026-07-01T17:00:00Z",
        "option_reasoning": "Quiet sushi option with strong timing margin."
      }
    ],
    "plan_summary": "Start with fresh sushi before the game."
  }
}
```

### Reservation Preview Response

```json
{
  "reservation_id": "2f5fc71b-4ccd-4239-8209-6aabb77e4a91",
  "status": "PREVIEW_PENDING",
  "restaurant_id": "rest-002",
  "party_size": 2,
  "reservation_time": "2026-07-01T17:00:00+00:00",
  "idempotency_key": "e2d21558-7fea-4903-98b3-6f589f8ce6f0"
}
```

## Current Limitations

- Restaurant, weather, directions, and reservation providers are still mocked
- Authentication and end-user identity management are not implemented
- Delivery channels such as SMS or email are not implemented
- The current CD workflow builds artifacts on `main` but does not deploy to a hosting target

## CI/CD

GitHub Actions workflows live in `.github/workflows/`:

- `ci.yml`
  Runs tests for pull requests and pushes to `main`

- `main.yml`
  Runs on pushes to `main`, builds Python artifacts, validates `docker compose config`, and uploads the build outputs
