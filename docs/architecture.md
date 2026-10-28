# SupportFlow architecture

The API and worker are separate processes in Compose. A single FastAPI application
contains bounded modules for sessions, tenancy, orders, knowledge, tickets and
approvals. PostgreSQL stores authoritative business and workflow state. Redis/Celery
schedules repeated scans of the SQL outbox; losing the broker does not lose queued jobs.

## Workflow states

A ticket starts open. Analysis creates a pending SQL job and increments its revision.
A worker claims a job with an atomic compare-and-set, a fresh lease token and expiry.
It snapshots the current ticket/order/documents, then calls the drafting provider
outside the transaction. Publication checks the lease token, ticket revision and
current job pointer. A manual edit/new job supersedes an old result.

Successful analysis yields a review state, exact sources, editable draft and, only
when deterministic policy permits it, an immutable return proposal. A proposal binds
the order, amount, currency, order version, policy version and ticket revision.

Approving requires current membership, operator/owner role, matching fingerprint,
unexpired pending state, unused-item confirmation and revalidated business eligibility.
The request record, proposal state, order version and audit event commit together.
Unique order/proposal constraints and row locks make repeat approvals idempotent.
This guarantees one local request record; external-provider exactly-once effects are
not claimed because this release has no external write connector.

Sending a reviewed reply records an operator message and closes the ticket. It does
not deliver email. Knowledge updates increment versions; old proposals then fail
revalidation.

## Failure behavior

- Crashed worker: another scan reclaims its expired lease.
- Stale worker: its old lease token cannot publish a new result.
- Failed provider: bounded retry delay; terminal failure after three attempts.
- Invalid model JSON/citations/numeric tokens: manual escalation; no proposed action.
- Changed order/policy/ticket: approval returns 409 and requires a fresh analysis.
- Duplicate approval: returns the existing local return request.
- Cross-tenant ID: returns 404 after organization membership/object checks.
- Concurrent approvals: PostgreSQL row locks serialize the same proposal; database
  uniqueness enforces one request per order.

## Trust boundaries

Ticket text and knowledge content are untrusted data. Generated text never selects a
tenant, grants a role or calls an execution tool. Policy routing is deliberately
restricted to a small structured knowledge base. The LLM adapter can suggest text
and quotes only. Source syntax checks do not guarantee factual meaning.

The return policy's days and displayed policy sentence are generated together on
owner updates, avoiding disagreement between an editable paragraph and execution
logic. Physical item condition still requires explicit operator confirmation.

Sessions are opaque tokens stored as hashes. CSRF tokens are HMAC-bound to the session.
Role/membership reads occur at request time. SQL data is tenant-scoped in application
queries; database administrators remain trusted. Real deployment requires an external
review of tenant isolation, retention, availability and operational controls.

## UI verification contract

Reference: generated SupportFlow workspace concept, 1536x1024. The implementation
preserves white/cool-gray surfaces, restrained teal, a navigation rail, inbox,
conversation and assistant inspector. It keeps controls as real HTML/React components.

Intentional differences: customer contact details and unmeasured confidence percentage
were removed; an explicit unused-item confirmation, backend/preview mode notice and
mobile profile menu were added because the real workflow requires them. Decorative
message attachment controls absent from this implementation were omitted.

The browser evidence should compare copy, panel structure, typography, colors, spacing
and mobile overflow. Browser-only preview actions are explicitly simulated. The CI
browser flow validates the actual backend separately.


## Verified v0.1 workflow

The release was checked against PostgreSQL 17 and Redis/Celery with Chrome at
1536x1024 and 390x844. The flow covered demo login, source-backed draft, operator
confirmation, reply, audit history, organization/role switching, literal HTML,
mobile profile controls and logout. Browser console errors: none.

Thirty API/agent tests passed on Python 3.11, 3.12 and 3.13; the additional PostgreSQL
integration test submitted four concurrent approvals and verified one request record.
SQLite/PostgreSQL migrations and the Docker build also passed.

Visual comparison used the generated 1536x1024 concept and the actual browser captures:
- Four-panel desktop structure and responsive detail/assistant stacking match the intended layout.
- White and cool-gray surfaces, teal actions and outlined icons remain consistent.
- Navigation, ticket heading, conversation, source and proposal retain the intended hierarchy.
- Typography and spacing remain readable at the desktop and 390px mobile viewport.
- Customer text stays literal; controls, checkboxes and mobile profile actions are real UI elements.

Intentional copy changes are listed above: synthetic-only contacts, no unmeasured
confidence percentage, explicit confirmation and accurate simulation notices. No
material clipping or horizontal overflow was found in the checked viewports.

[CI and screenshot artifacts](https://github.com/55AIAI/supportflow-ai/actions/runs/40640423557)
