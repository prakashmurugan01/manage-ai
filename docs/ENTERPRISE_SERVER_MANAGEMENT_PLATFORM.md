# Enterprise Server Management Platform

## 1. Architecture Plan

ManageAI is organized as a Django REST Framework control plane with Django Channels for realtime events, Celery for scheduled collection, Redis for broker/channel backing, PostgreSQL for durable state, and React for the operator console.

Production server monitoring uses three data paths:

- Local collector: the backend host is discovered through `/api/servers/discover-local/` and collected with `psutil`.
- Remote agent ingestion: Windows, Linux, VPS, dedicated, physical, and cloud servers post real telemetry to `/api/servers/{id}/ingest-metrics/`.
- Remote reachability probe: SSH/SFTP/SMB/WinRM/REST/WebSocket endpoints are checked over their configured port. The platform does not invent CPU/RAM/disk metrics for these servers until a credentialed collector or agent submits telemetry.

Realtime updates flow through `/ws/server-monitor/` and broadcast `initial`, `metrics_update`, `server_updated`, and `servers_update` messages.

## 2. Database Design

Primary server entities:

- `server_monitor.Server`: registered server identity, IP, hostname, server type, connection method, OS, CPU/memory capacity, status, health score, last heartbeat, and last connection error.
- `server_monitor.ServerMetrics`: timestamped CPU, CPU temperature, per-core usage, RAM, disk, network, latency, packet loss, process count, and service count.
- `server_monitor.DiskMount`: timestamped disk mount capacity and utilization.
- `remote_access.RemoteDevice`, `RemoteSession`, `RemoteTransfer`: remote agent device/session/transfer control.
- `file_tracking.FileTransfer`, `FileEvent`, `FileAlert`, `DiskVolume`, `TrackingRule`: audited disk movement tracking and risk detection.
- `hosting.ProjectUpload`, `DeploymentRun`: project upload, analysis, deployment run, logs, and provider deployment state.

Secrets must remain encrypted at rest and must not be returned from serializers.

## 3. API Design

Server monitoring:

- `GET /api/servers/`
- `POST /api/servers/`
- `GET /api/servers/summary/`
- `POST /api/servers/discover-local/`
- `POST /api/servers/collect-now/`
- `GET /api/servers/{id}/metrics/?hours=2`
- `GET /api/servers/{id}/disks/`
- `POST /api/servers/{id}/ingest-metrics/`
- `POST /api/servers/{id}/toggle-power/`

Disk transfer:

- `GET /api/v1/file-tracking/dashboard/`
- `POST /api/v1/file-tracking/transfers/`
- `GET /api/v1/file-tracking/events/`
- `GET /api/v1/file-tracking/alerts/`

Deployment:

- `POST /api/hosting/uploads/`
- `GET /api/hosting/uploads/{id}/`
- `POST /api/hosting/uploads/{id}/deploy/`
- `GET /api/hosting/deployments/{id}/`
- `POST /api/hosting/deployments/{id}/redeploy/`

## 4. Backend Implementation

Implemented production slice:

- Real local machine discovery using OS, hostname, CPU, and memory data.
- Real local telemetry collection with `psutil`.
- Non-local servers are probed for actual connectivity only.
- Agent/API telemetry ingestion persists and broadcasts real metrics.
- Celery beat is configured for one-second metric collection.
- WebSocket broadcasts server and metric changes.

Required production adapters:

- SSH/SFTP collector with key-based authentication.
- WinRM collector with certificate/TLS validation.
- SMB file manager adapter.
- Cloud provider collectors for AWS, Azure, GCP, DigitalOcean, Vercel, Netlify, Railway, Render, cPanel, Plesk, and Hostinger.

## 5. Frontend Implementation

Implemented production slice:

- Server Monitor page uses real `/api/servers/` data.
- WebSocket live state overlays REST data.
- Empty state shows `SERVER NOT FOUND` with diagnostics and local discovery.
- Live detail view shows CPU, RAM, disk, health, network, chart history, and disk mounts only when real data exists.
- Disk Transfer form no longer ships with demo values.

## 6. WebSocket Implementation

Current channel:

- `/ws/server-monitor/?token=<jwt>`

Messages:

- `initial`: current server list and last metrics.
- `metrics_update`: persisted server metrics.
- `server_updated`: one server status change.
- `servers_update`: batch server status changes.

## 7. Real Server Connectivity

Supported registration methods are modeled now:

- Local agent
- Remote agent
- SSH
- SFTP
- SMB
- WinRM
- REST API
- WebSocket

Only local and agent/API ingestion currently produce full live metrics. Other methods perform real reachability checks until secure provider-specific collectors are added.

## 8. Disk Transfer Engine

Existing remote access transfer code supports chunked uploads/downloads and progress broadcasting. File tracking records audited transfers and risk. Next production step is to bind remote agent transfer progress into `file_tracking.FileTransfer` so every agent transfer updates the enterprise tracking dashboard automatically.

## 9. Deployment Engine

Existing hosting deployment supports upload analysis, provider recommendation, and Vercel uploaded-package deployment. Next production step is adapter parity for SSH/VPS, cPanel, Plesk, Render, Railway, DigitalOcean, AWS, Azure, and GCP.

## 10. Testing Plan

Backend:

- Model migration tests for server metric fields.
- API tests for local discovery, collect-now, metric ingestion, server summary, and permission enforcement.
- WebSocket tests for initial payload and broadcast payloads.
- Collector tests with mocked `psutil` and socket probe outcomes.

Frontend:

- Server Monitor empty state test.
- Live metric merge test for WebSocket payloads.
- Add server form validation test.
- Disk transfer form should start empty and require source/destination/size/status.

Operations:

- Run Django with PostgreSQL, Redis, Celery worker, Celery beat, and ASGI server.
- Configure TLS termination at Nginx.
- Store provider credentials only in environment/secret manager.
