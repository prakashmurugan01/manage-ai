# Enterprise Project Intelligence Platform

## High-Level Architecture

The platform is a centralized command center for monitoring and controlling projects across localhost machines, remote laptops, VPS servers, containers, Kubernetes clusters, and production infrastructure.

```
Developer Machine / Server
  Project Intelligence Agent
    - project discovery
    - runtime metrics
    - Git/build/deploy signals
    - logs and webhook execution traces
    - controlled command execution
        |
        | Secure WebSocket / HTTPS ingest
        v
Django ASGI Edge
  Django REST Framework APIs
  Django Channels WebSockets
  RBAC/JWT/API key middleware
        |
        v
Event and Data Plane
  PostgreSQL: durable inventory, events, audit records
  Redis: channel layer, cache, rate counters, command fanout
  Celery: stale-agent detection, analytics, AI jobs, retries
        |
        v
Enterprise UI
  Project Intelligence Command Center
  Project workspace
  Webhook inspector
  Agent registration and revocation
```

## System Design

Core services:

- Control plane: authenticated REST APIs for registration, project workspaces, command creation, revocation, and reporting.
- Data plane: agent snapshots, metrics, logs, deployment signals, webhook traces, and command results.
- Realtime plane: Django Channels groups for dashboard updates and agent command delivery.
- AI intelligence layer: deterministic first-pass analysis for latency, signature failures, failed webhooks, saturation, and deployment risk, ready for LLM-based expansion.
- Security plane: JWT users, hashed agent tokens, tenant-scoped querysets, redaction of sensitive headers, command allowlists, and audit-ready persisted events.

## Agent Architecture

Implemented agent:

- File: `backend/agents/project_intelligence_agent.py`
- Transport: WebSocket to `/ws/project-agent/?token=...`
- Discovery: React, Next.js, Django, Node.js, Laravel, and Spring Boot.
- Telemetry: CPU, memory, disk, network rates, process count, container hints.
- SCM: branch, commit SHA, commit message, author, commit date, remote URL.
- Logs: common framework log files with bounded ingestion and severity extraction.
- Commands: refresh discovery and collect logs by default; build/deploy/restart/rollback only when started with `--allow-control` and safe mappings exist.

Lifecycle:

```
Register agent in UI
  -> server creates hashed token and returns one-time plaintext token
Start agent with token
  -> WebSocket connect
  -> server authenticates token hash
  -> agent sends snapshot
  -> backend upserts projects and telemetry
  -> dashboard receives realtime event
  -> server returns queued commands
  -> agent executes allowed commands
  -> agent returns command.result
```

Authentication flow:

- Human users authenticate with JWT.
- Agents authenticate with `mai_agent_*` token.
- Server stores only SHA-256 token hash and token prefix.
- Revoked agents are denied during WebSocket and HTTPS ingest.

Heartbeat:

- Agent sends heartbeat every configured interval, default 15 seconds.
- Backend marks agent `online` and updates `last_seen_at`.
- Celery task `apps.project_intelligence.tasks.mark_stale_project_agents` runs every 15 seconds.
- Agents older than the stale threshold are marked `offline`.

Reconnect:

- Agent uses exponential backoff from 1 second to 60 seconds.
- WebSocket ping interval is 20 seconds.
- Snapshot replay after reconnect makes the backend eventually consistent.

## Database Schema

Implemented Django models:

- `MachineAgent`: machine identity, owner, environment, status, token prefix/hash, capabilities, metadata, last seen.
- `ManagedProject`: discovered project inventory, framework, environment, runtime, Git, build, deployment, health.
- `RuntimeMetric`: CPU, memory, disk, network, active users, requests/sec, error rate, latency, process/container counts.
- `ProjectLogEntry`: severity, source, message, trace ID, metadata, timestamp.
- `DeploymentSignal`: build/deployment/rollback/readiness signals, release ID, risk score, summary.
- `ProjectWebhookEvent`: incoming/outgoing events, status, headers, bodies, retry history, execution trace, signature validity, threat score, AI analysis.
- `AgentCommand`: queued/sent/succeeded/failed command workflow with payload, result, requester, expiry.

Indexes:

- Agent status by environment.
- Project environment/runtime, framework/build, deployment/update time.
- Metrics by project and recorded time.
- Webhooks by status/time and integration/event type/time.
- Logs by project, level, timestamp.
- Commands by agent, status, created time.

## Event Flow Diagrams

Agent snapshot:

```
Agent discovers projects
  -> samples runtime metrics
  -> tails bounded logs
  -> sends snapshot over WebSocket
  -> Channels consumer authenticates token
  -> ingest_agent_payload upserts data in PostgreSQL
  -> Redis channel layer broadcasts agent.ingested
  -> React Query invalidates dashboard cache
  -> UI refreshes counters, charts, topology, logs
```

Webhook event:

```
Webhook source
  -> integration endpoint or agent trace
  -> ProjectWebhookEvent persisted
  -> sensitive fields redacted
  -> signature and threat signals evaluated
  -> AI analysis stored
  -> dashboard event stream updates
  -> operator inspects payload and retry history
  -> retry command queued when agent context exists
```

Command flow:

```
Operator clicks command in workspace
  -> POST /api/project-intelligence/projects/{id}/command/
  -> AgentCommand queued with expiry
  -> next agent heartbeat receives commands
  -> agent checks allow_control and safe command mapping
  -> command executes or is rejected
  -> command.result sent over WebSocket
  -> backend stores result and completion time
```

## API Specifications

REST APIs:

- `GET /api/project-intelligence/dashboard/`
  - Query: `environment`, `status`, `window_hours`
  - Returns: summary, agents, projects, traffic, webhooks, logs, deployments, topology, anomalies.
- `POST /api/project-intelligence/agents/register/`
  - Auth: JWT
  - Body: `name`, `machine_id`, `environment`, `hostname`, `os_name`, `capabilities`, `metadata`
  - Returns: agent record and one-time `plaintext_token`.
- `POST /api/project-intelligence/agents/ingest/`
  - Auth: `Authorization: Agent <token>`
  - Body: heartbeat, projects, metrics, logs, deployment_signals, webhook_events.
  - Returns: ingest counts and queued commands.
- `GET /api/project-intelligence/projects/`
  - Filters: environment, runtime_status, build_status, deployment_status, framework.
- `GET /api/project-intelligence/projects/{id}/workspace/`
  - Returns: project, recent metrics, logs, webhooks, deployments, commands.
- `POST /api/project-intelligence/projects/{id}/command/`
  - Body: `command_type`, `payload`.
- `GET /api/project-intelligence/webhooks/`
  - Filters: project, status, direction, integration, event_type, signature_valid.
- `POST /api/project-intelligence/webhooks/{id}/retry/`
  - Queues retry command when agent context exists.
- `POST /api/project-agents/{id}/revoke/`
  - Revokes machine identity.

WebSocket APIs:

- `/ws/project-intelligence/?token=<jwt>`
  - Human dashboard stream.
  - Receives `project.event` payloads.
- `/ws/project-agent/?token=<agent_token>`
  - Machine agent stream.
  - Sends `snapshot`, `heartbeat`, `telemetry`, `command.result`.
  - Receives `ingest.accepted` with queued commands.

## Security Architecture

Controls implemented:

- JWT authentication for user APIs and dashboard WebSockets.
- Agent machine authentication with one-time plaintext token display and hashed server storage.
- Agent revocation.
- Tenant-scoped querysets for agents, projects, webhooks, metrics, logs, deployments, and commands.
- Sensitive key redaction for authorization headers, cookies, API keys, tokens, secrets, and passwords.
- Command execution allowlist in the agent.
- No arbitrary shell command execution from server payloads.
- Webhook signature validity field and threat scoring support.
- Audit-ready event tables with timestamps and user/agent associations.

SOC2 readiness path:

- Add immutable audit appenders for every command, revocation, registration, retry, and payload inspection.
- Enforce organization/team RBAC over agent ownership.
- Add IP allowlists and mTLS for production agents.
- Store agent tokens with rotating signing keys or HSM-backed hash pepper.
- Retain raw webhook payloads in encrypted storage with field-level retention policies.
- Add rate limiting per agent, per tenant, and per endpoint.

## AI Intelligence Layer

Implemented deterministic signals:

- Failed or blocked webhook detection.
- Response code failure detection.
- Latency spike detection above 2000 ms.
- Signature failure detection.
- Threat score escalation.
- Project health degradation from runtime/build/deployment/metrics.
- Critical log correlation.
- CPU saturation risk.

Expansion points:

- Complaint detection from webhook payloads and API events.
- Sentiment classification.
- Failure prediction from rolling metrics.
- Deployment risk analysis from commit, build, incident, and error-rate deltas.
- Smart ticket routing by owning team, project, framework, and severity.

## UI Wireframes

Command center:

```
+---------------------------------------------------------------------+
| Project Intelligence Command Center                                 |
| live websocket | 24h window | online agents                         |
| [agents] [projects] [running] [degraded] [webhook failures] [errors]|
+---------------------------------------------------------------------+
| search | environment | status | window | refresh                    |
+---------------------------------------+-----------------------------+
| Realtime Runtime Fabric               | Register Machine Agent       |
| CPU / memory / error chart            | Distributed Agents           |
+---------------------------------------+ Topology Map                 |
| Discovered Projects Table             | AI Operations Signals        |
+---------------------------------------+ Deployment Timeline          |
| Webhook Command Center                |                             |
+---------------------------------------+                             |
| Runtime Logs                          |                             |
+---------------------------------------+-----------------------------+
```

Project workspace:

```
+---------------------------------------------------------------------+
| Project name | framework | environment | agent | close              |
| health | runtime | branch | build | deploy                          |
| refresh | collect logs | build | deploy | rollback                  |
| Runtime metrics chart           | Command history                   |
| Webhook events | Runtime logs | Deployments                         |
+---------------------------------------------------------------------+
```

Webhook inspector:

```
+---------------------------------------------------------------------+
| Event type | project | integration | timestamp | close              |
| status | direction | processing time | signature | threat           |
| Request headers     | Request body                                  |
| Response body       | AI analysis                                   |
| Retry history       | Execution trace                               |
| Retry Event                                                         |
+---------------------------------------------------------------------+
```

## Folder Structure

Implemented files:

```
backend/apps/project_intelligence/
  __init__.py
  admin.py
  apps.py
  consumers.py
  migrations/0001_initial.py
  models.py
  routing.py
  serializers.py
  services.py
  tasks.py
  tests.py
  urls.py

backend/agents/
  project_intelligence_agent.py

frontend/src/pages/
  ProjectIntelligence.jsx

docs/
  PROJECT_INTELLIGENCE_PLATFORM.md
```

Modified platform wiring:

```
backend/manage_ai/settings.py
backend/manage_ai/urls.py
backend/manage_ai/asgi.py
backend/requirements.txt
frontend/src/App.jsx
frontend/src/components/layout/Sidebar.jsx
frontend/src/constants/navigation.js
```

## Backend Implementation Plan

Completed:

- Project Intelligence Django app.
- Data model and migration.
- Agent registration and hashed token flow.
- Agent HTTPS ingest and WebSocket ingest.
- Dashboard aggregation API.
- Project workspace API.
- Command queue API.
- Webhook retry API.
- Stale-agent Celery task.
- Tenant isolation tests.

Next production hardening:

- PostgreSQL time-series partitioning for `RuntimeMetric`, `ProjectLogEntry`, and `ProjectWebhookEvent`.
- Organization-level RBAC beyond owner-level scoping.
- API rate limiting for agent ingest and dashboard APIs.
- Dedicated command audit table with immutable hash chain.
- Celery jobs for AI enrichment and anomaly rollups.
- Data retention policies by environment and severity.

## Frontend Implementation Plan

Completed:

- First-class `/project-intelligence` route.
- Sidebar and navigation entry.
- Premium dark SaaS command center.
- Live WebSocket invalidation.
- Agent registration token modal.
- Runtime charts.
- Project inventory table.
- Webhook command center and payload inspector.
- Project workspace modal with command dispatch.
- Agents panel with revocation.
- Topology and AI signal panels.

Next production hardening:

- Virtualized tables for tens of thousands of projects/events.
- Saved views per team/environment.
- Role-based command button visibility.
- Incident routing panel.
- Timeline drilldowns with trace correlation.
- Keyboard shortcut command palette.

## Deployment Architecture

Recommended production topology:

```
Internet / Private Network
  -> WAF / Load Balancer
  -> ASGI WebSocket pool (Daphne/Uvicorn workers)
  -> WSGI/ASGI API pool
  -> Redis Cluster for Channels and Celery broker
  -> PostgreSQL primary plus read replicas
  -> Celery worker pools
  -> Object storage for large payload archives
  -> Observability stack: Prometheus, Grafana, Loki, OpenTelemetry
```

Docker/Kubernetes:

- Separate deployments for API, ASGI WebSocket workers, Celery workers, Celery beat, and frontend.
- HorizontalPodAutoscaler for WebSocket pods based on active connections and event loop latency.
- PodDisruptionBudgets for WebSocket and Celery pools.
- Redis Cluster or managed Redis with sharding.
- PostgreSQL with connection pooling through PgBouncer.
- Secrets via Kubernetes Secrets or external secret manager.

## Scalability Strategy

Target: 100,000+ concurrent connections.

- Split WebSocket workers from API workers.
- Use sticky load balancing only when required; Channels groups work through Redis.
- Shard agents by tenant or region across Redis channel layers at higher scale.
- Keep agent messages bounded and compressed at the edge when payloads grow.
- Persist high-volume metrics in partitioned tables.
- Roll up metrics into minute/hour aggregates for dashboard queries.
- Keep live dashboard responses capped and cursor-based for deep inspection.
- Move AI enrichment to Celery queues with backpressure.
- Use bulk insert paths for very high-frequency metric ingestion.
- Place webhook payload bodies in encrypted object storage when payload size exceeds database thresholds.

## Production-Ready Code Map

Backend:

- `services.ingest_agent_payload`: transactional ingestion, redaction, project upsert, metric/log/webhook persistence, AI analysis, broadcast.
- `services.authenticate_agent_token`: machine auth using hashed tokens.
- `views.ProjectIntelligenceDashboardView`: scoped aggregation API for command center.
- `views.ManagedProjectViewSet.workspace`: dedicated project workspace payload.
- `consumers.ProjectAgentConsumer`: secure agent WebSocket protocol.
- `tasks.mark_stale_project_agents`: reliability loop for heartbeat expiry.

Frontend:

- `ProjectIntelligence.jsx`: live dashboard, charts, agent registration, project workspace, webhook inspector, command queueing.
- `App.jsx`: first-class protected route.
- `Sidebar.jsx` and `navigation.js`: discoverable module entry.

Agent:

- `project_intelligence_agent.py`: real filesystem/framework discovery, process matching, telemetry sampling, Git enrichment, log capture, reconnect strategy, safe command execution.
