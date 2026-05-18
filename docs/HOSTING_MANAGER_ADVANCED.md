# Hosting Manager Advanced Platform

## Folder Structure

- `backend/apps/hosting/models.py` - hosted projects, lifecycle timeline, hosting API keys, usage logs.
- `backend/apps/hosting/serializers.py` - secure write-only access key handling and API response shapes.
- `backend/apps/hosting/views.py` - Django REST endpoints for CRUD, dashboard, timeline, archive/restore, export, and external status.
- `backend/apps/hosting/tasks.py` - Celery health checks, lifecycle automation, unstable-server flagging.
- `frontend/src/pages/HostingManager.jsx` - dark SaaS control center UI, table/card views, timeline, API keys, command palette.

## Database Schema

### HostedProject

Stores client name, project name, domain, hosting platform, hosting URL, optional server IP, encrypted access key metadata, link toggle state, server health, uptime percentage, expiry date, revenue, tag, and archive state.

### HostingLifecycle

Tracks created, updated, renewed, expired, archived, restored, health-check, link-disabled, and API-key-created events for each hosted project.

### HostingProjectApiKey

Stores encrypted per-project external API keys with role-based access (`admin`, `client`), active state, rate limit, expiry, and last-used timestamp.

### HostingApiUsageLog

Captures external API usage by key, endpoint, method, IP, response code, response time, and timestamp.

## API Endpoints

- `GET/POST /api/hosting/` - list and create hosted projects.
- `GET/PATCH/DELETE /api/hosting/{id}/` - retrieve, update, delete.
- `POST /api/hosting/{id}/renew/` - one-click renew hosting.
- `POST /api/hosting/{id}/archive/` - archive expired or inactive projects.
- `POST /api/hosting/{id}/restore/` - restore archived projects.
- `GET /api/hosting/{id}/timeline/` - lifecycle timeline.
- `POST /api/hosting/{id}/toggle_link/` - ON/OFF hosting URL.
- `POST /api/hosting/{id}/health-check/` - queue immediate server check.
- `GET /api/hosting/summary/` - control-center metrics.
- `GET /api/hosting/dashboard/` - uptime graph, expiry trends, AI-style insights.
- `GET /api/hosting/export/` - CSV report export.
- `GET /api/hosting/external-status/` - external project status using `Authorization: API_KEY host_...`.
- `GET/POST /api/hosting-api-keys/` - manage project API keys.
- `POST /api/hosting-api-keys/{id}/regenerate/` - rotate a key.
- `POST /api/hosting-api-keys/{id}/toggle/` - enable or disable a key.
- `GET /api/hosting-api-keys/{id}/logs/` - usage logs.

## Background Workers

Celery Beat schedule:

- `hosting.tasks.check_all_hosted_project_health` every 60 seconds.
- `hosting.tasks.update_hosting_lifecycle_statuses` daily at 09:10.
- `apps.notifications.tasks.check_hosting_expiry` daily at 09:00.

Smart actions:

- Offline health checks turn hosting links OFF.
- Expired projects are marked expired and archived.
- Repeated downtime flags projects as maintenance.

## React Components

The Hosting Manager page contains:

- Metrics cards for projects, servers, down servers, expiring projects, live links, and monthly revenue.
- Smart global search command palette.
- Table and card views.
- Project add/edit modal.
- Lifecycle timeline modal.
- API key management modal.
- Uptime and expiry trend charts.
- AI insights and reminder panels.

## Security

- JWT authentication protects dashboard APIs.
- Sensitive hosting access keys and external API keys are encrypted with Fernet.
- External status access uses per-project API keys with role and rate limiting.
- Audit logs record create, update, delete, renew, archive, restore, export, and API key actions.

## Deployment Steps

1. Install backend dependencies: `pip install -r backend/requirements.txt`.
2. Set `FIELD_ENCRYPTION_KEY` or `API_KEY_FERNET_KEY` in production.
3. Run migrations: `python backend/manage.py migrate`.
4. Start Redis for Celery, cache, and channels.
5. Start backend: `python backend/manage.py runserver`.
6. Start worker: `celery -A manage_ai worker -l info`.
7. Start beat: `celery -A manage_ai beat -l info`.
8. Start frontend: `npm run dev` from `frontend`.
