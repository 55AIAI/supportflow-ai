# SupportFlow AI

[![Checks](https://github.com/55AIAI/supportflow-ai/actions/workflows/checks.yml/badge.svg)](https://github.com/55AIAI/supportflow-ai/actions/workflows/checks.yml)

A multi-tenant support workspace with source-backed drafts, human-approved return
requests, durable background jobs and a React interface. Built with FastAPI,
SQLAlchemy, PostgreSQL, Redis/Celery, React and TypeScript.

**AI proposes. An operator reviews. The server validates and executes the exact action.**

[Open the owner-only visual preview](https://supportflow-ai-demo-55aiai.nurtasmuhanbetov91.chatgpt.site)
 · [Verified end-to-end run](https://github.com/55AIAI/supportflow-ai/actions/runs/40640423557)

The hosted preview simulates actions in the browser. Run Docker below for the complete
Python API, PostgreSQL and Redis/Celery application.


## Run the complete application

Docker Desktop/Engine with Compose:

```bash
git clone https://github.com/55AIAI/supportflow-ai.git
cd supportflow-ai
python scripts/init_env.py
docker compose up --build
```

Open **http://localhost:5080** and choose **Открыть демо-магазин**.
The setup script generates random secrets in an ignored local .env; it does not print
them or overwrite an existing file. Compose starts PostgreSQL, Redis, migrations, API,
Celery worker and scheduler. The web app and API share the same origin.

Each demo login creates a fresh sandbox with two organizations, six synthetic orders
and six tickets per organization. Switch organizations and demo roles in the sidebar;
on mobile, use the profile menu. Demo role switching is available only in an explicitly
enabled demo organization.

## Try the main flow

1. Open **Возврат заказа №1042** in Aster Store.
2. Choose **Подготовить ответ**. A durable job checks the order and current rules.
3. Inspect the exact source quote and proposed order/amount.
4. Confirm the unused-item check and choose **Подтвердить возврат**.
5. Send the reviewed reply; inspect **История**.
6. Switch to North Supply: its rules and history are separate.
7. Choose the viewer role: mutation controls and server permissions deny writes.

A return request is a local record in the simulated store. No payment is refunded,
external shop changed, or email sent. Replies are stored in the ticket conversation.
This is an intentionally bounded commerce adapter suitable for a public demonstration.

## Local development without Docker

Python 3.11-3.13 and Node 22+:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run build
cd ../backend
python -m supportflow.demo
```

Open http://127.0.0.1:5080. This convenience command creates an isolated SQLite demo
database under backend/data, generates a process-local session signing secret, and
runs the SQL job poller in an application thread. Restarting this convenience mode
invalidates sessions; the Compose configuration uses a stable secret from .env.

For Vite hot reload, set APP_ORIGIN to the exact Vite origin before starting the API;
Vite proxies /api to 127.0.0.1:5080. The built single-origin mode needs no CORS setup.

## Implemented boundaries

| Concern | Contract |
|---|---|
| Tenant access | Every organization endpoint checks current membership; object lookups also scope the organization |
| Roles | Owner: knowledge + operations; operator: ticket operations; viewer: read only |
| Authentication | Opaque revocable session cookies, HttpOnly, SameSite=Strict, 8-hour expiry; scrypt passwords |
| Request protection | Same-origin checks, custom request header, CSRF token, 64 KiB request limit |
| Proposal approval | Immutable payload fingerprint, 15-minute expiry, current ticket/order/policy versions, server policy revalidation |
| Duplicate execution | SQL unique constraints on return order and proposal; approval retries return the existing request |
| Jobs | Durable SQL queue, 60-second leases, guarded publication, at most 3 attempts, bounded retry delay |
| Broker recovery | Celery beat drains SQL jobs periodically; Redis is a delivery aid, not the source of job state |
| Evidence | Exact document quotes and source versions; unsupported LLM output is rejected |
| Audit | Append-only application API; no message text in audit details |
| UI | Inbox, conversation, assistant review, knowledge, orders, audit and policy checks; responsive layout |

PostgreSQL transactions/row locks implement concurrent approvals. SQLite serializes
API writes in demo mode. These are application authorization boundaries; PostgreSQL
row-level security is not configured, and a database administrator can change audit
records. The audit log is not claimed to be tamper-proof.

## AI modes

**demo** is the default: deterministic templates, fixed topic routing and exact policy
quotes. It requires no API key and makes no LLM-quality claim. Return eligibility always
comes from server-side policy, not generated text.

**ollama** optionally drafts text with a local model:

```text
AI_PROVIDER=ollama
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

Run Ollama and obtain the chosen model yourself before enabling this mode. The
application does not download weights. The model receives the current ticket, order
and selected knowledge document; use a trusted local endpoint for private data.
On Linux, configure the reachable host endpoint explicitly.

Model output is constrained to answer/citations, exact quotes are checked, and numeric
tokens must occur in supplied facts. These checks do **not** prove semantic correctness:
an operator must review every answer. The model has no execution tools and cannot
approve its own proposal. Provider transport failures retry; rejected output is shown
explicitly for manual review. Token counts are recorded only when the provider returns
them; no cost or confidence numbers are invented.

This first release uses a small structured knowledge base with topic selection.
Semantic vector retrieval, external commerce connectors, distributed rate limiting,
organization invitations, advanced agent graphs and production observability are
future extensions, not features claimed by this version.

## Browser-only visual preview

A separate private Sites preview runs the same React interface with VITE_DEMO_ONLY=1.
Its banner explicitly says server actions are simulated. It stores synthetic sandbox
state in sessionStorage, has no production authorization guarantee and does not run
the Python policy tests. It is for reviewing the UI; use Docker for the complete system.

## Checks

```bash
cd backend
python -m unittest discover -s tests -v
alembic upgrade head
alembic check
```

CI runs Python 3.11/3.12/3.13 tests and migrations, builds the frontend and Docker image,
checks production npm dependencies, and exercises concurrent approvals on a dedicated
PostgreSQL database. The browser workflow runs Chrome at 1536x1024 and 390x844 against
the real API, PostgreSQL and Redis/Celery. It covers source-backed draft, approval,
reply, history, tenant switch, roles, ticket creation, literal HTML and mobile logout.

The UI's **Проверки** page runs 12 deterministic return-policy scenarios, including
expiry boundaries, wrong customer, missing rules and future dates. It is not an LLM
accuracy benchmark. Live Ollama inference and full production deployment require
separate environment validation.

## API and operational notes

- OpenAPI: /docs. Readiness: /health/ready. Liveness: /health/live.
- All business routes are under /api/orgs/{organization_id}/...
- Mutations require X-SupportFlow: 1 and the X-CSRF-Token returned by session/login.
- SSE ticket updates recheck session and membership while streaming.
- Listing endpoints return up to 200 records; pagination/search indexing are future work.
- Login/demo throttling is bounded and process-local. Configure shared limits at the
  edge before public hosting.
- For a real deployment, disable SUPPORTFLOW_DEMO, use HTTPS with COOKIE_SECURE=1,
  configure APP_ORIGIN, database backups, retention, monitoring and secret management.
- Demo sandboxes are not automatically purged in this release. Do not expose an
  unbounded public sandbox without retention and shared rate limits.

## Layout

```text
backend/supportflow/     API, auth, models, policy, agent, durable jobs
backend/migrations/      Explicit Alembic schema
backend/tests/           API, agent contracts and PostgreSQL concurrency
frontend/src/            React app, API adapter, isolated visual preview adapter
scripts/                 Setup and browser workflow
compose.yml              PostgreSQL + Redis + API + Celery
docs/architecture.md     State transitions and failure contracts
```
