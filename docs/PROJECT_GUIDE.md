# ManageAI Complete Project Guide

This guide is the main handoff document for running, accessing, maintaining, and moving ManageAI to production. It is written for developers, admins, deployment engineers, and project owners who need a step-by-step operating manual.

## 1. Project Summary

ManageAI is a full-stack internal SaaS platform for project delivery, hosting management, project intelligence, server monitoring, tickets, deployment control, remote access, file tracking, notifications, API monitoring, AI assistance, and enterprise settings.

The platform is made of:

- Frontend: React 18, Vite, Tailwind CSS, Framer Motion, React Router, Axios, Recharts, Three.js.
- Backend: Django 4.2, Django REST Framework, Simple JWT, Channels, Daphne, Celery, Redis, WhiteNoise.
- Realtime layer: WebSocket consumers for events, notifications, server monitoring, API monitoring, remote access, file transfer, and project intelligence.
- Background processing: Celery worker and Celery beat for monitoring, hosting sync, provider checks, metrics, and notifications.
- Storage: SQLite for local/default runs, MySQL supported through `DB_ENGINE=mysql`, media storage under backend `media`.
- Production packaging: Dockerfiles for backend and frontend, plus `docker-compose.yml` with Redis, backend, frontend, and persistent volumes.

## 2. Repository Map

```text
manage ai/
  backend/
    manage.py
    manage_ai/
      settings.py
      urls.py
      asgi.py
      celery.py
    apps/
      accounts/
      projects/
      tasks/
      tickets/
      deployments/
      notifications/
      enterprise/
      realtime/
      server_monitor/
      hosting/
      api_monitor/
      project_intelligence/
      remote_access/
      file_tracking/
      modules/
      core/
      crm/
      erp/
      hr/
      inventory/
      webhooks/
      ai_layer/
  frontend/
    src/
      App.jsx
      api/
      components/
      constants/navigation.js
      context/
      pages/
      realtime/
      utils/
    vite.config.ts
    package.json
  docs/
  docker-compose.yml
```

## 3. Required Tools

Install these before running the project locally:

- Python 3.12 recommended.
- Node.js 20 recommended.
- npm.
- Redis for realtime and Celery production-like local runs.
- Git.
- Docker Desktop if using the Docker path.

Windows PowerShell examples are used below because this project is currently being developed on Windows.

## 4. Environment Files

Create local environment files from the examples:

```powershell
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

For local development with the current Vite proxy, make sure:

```env
# backend/.env
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5175,http://127.0.0.1:5175
USE_INMEMORY_CHANNELS=True
DB_NAME=manageai.sqlite3
```

```env
# frontend/.env
VITE_API_BASE_URL=/api
VITE_WS_URL=ws://127.0.0.1:8001/ws/events/
```

Important production variables:

```env
DJANGO_SECRET_KEY=use-a-long-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
USE_INMEMORY_CHANNELS=False
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
FIELD_ENCRYPTION_KEY=use-a-valid-fernet-key
API_KEY_FERNET_KEY=use-a-valid-fernet-key
```

Optional provider variables exist for GitHub, Vercel, Netlify, Cloudflare, AWS, Azure, GCP, DigitalOcean, Hostinger, GoDaddy, cPanel, Plesk, Railway, Render, Firebase, and Supabase. Only enable the providers the production instance actually uses.

## 5. Local Backend Setup

Run the backend on port `8001`. The frontend Vite config proxies `/api`, `/media`, and `/ws` to `127.0.0.1:8001`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8001
```

Open the backend health check:

```text
http://127.0.0.1:8001/
```

Optional server-monitor demo data:

```powershell
python manage.py seed_data
```

## 6. Local Frontend Setup

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5175
```

The important local pages are:

| Page | URL |
| --- | --- |
| Login | `http://localhost:5175/login` |
| Dashboard | `http://localhost:5175/dashboard` |
| Projects | `http://localhost:5175/projects` |
| Settings | `http://localhost:5175/settings` |
| Hosting Manager | `http://localhost:5175/hosting` |
| Deploy Project | `http://localhost:5175/hosting/deploy` |
| Project Intelligence | `http://localhost:5175/project-intelligence` |
| Server Monitor | `http://localhost:5175/server-monitor` |
| Remote Access | `http://localhost:5175/remote-access` |
| Disk Transfer | `http://localhost:5175/file-tracking` |
| API Keys | `http://localhost:5175/api-keys` |
| API Monitor | `http://localhost:5175/api-monitor` |
| Tickets | `http://localhost:5175/tickets` |
| Notifications | `http://localhost:5175/notifications` |
| Users | `http://localhost:5175/users` |
| Logs | `http://localhost:5175/logs` |

## 7. Demo Login Accounts

After `python manage.py seed_demo`, use:

| Role | Email | Password |
| --- | --- | --- |
| Super Admin | `super@manageai.local` | `ManageAI@12345` |
| Admin | `admin@manageai.local` | `ManageAI@12345` |
| Developer | `dev@manageai.local` | `ManageAI@12345` |
| Client | `client@manageai.local` | `ManageAI@12345` |

Super Admin and Admin can access the Settings page. Logs and Monitoring are Super Admin only.

## 8. Authentication Flow

1. User logs in through `/login`.
2. Frontend calls `/api/auth/login/`.
3. Backend returns JWT access and refresh tokens.
4. Frontend stores tokens in `localStorage`.
5. Axios attaches `Authorization: Bearer <access-token>` to API requests.
6. If a request returns `401`, the frontend calls `/api/auth/refresh/`.
7. Protected routes check user role before showing restricted pages.

Main auth endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/api/auth/login/` | Login and issue JWT tokens |
| `/api/auth/refresh/` | Refresh access token |
| `/api/auth/verify/` | Verify token |
| `/api/auth/me/` | Current user profile |
| `/api/auth/me/avatar/` | Upload current user avatar |
| `/api/auth/register/` | Register user |
| `/api/auth/face-login/` | Face login |
| `/api/auth/face-enroll/` | Face enrollment |

## 9. Role Access Model

The project uses role-based access control from the backend user role and frontend protected routes.

| Role | Intended Access |
| --- | --- |
| Super Admin | Full platform control, users, logs, monitoring, settings, API monitor |
| Admin | Project, ticket, deployment, settings, user operations |
| Developer | Assigned projects, tasks, tickets, development activity |
| Client | Client project visibility, tickets, approved files, progress visibility |

Settings also includes page/module access control through:

- `/api/settings/modules/`
- `/api/settings/access-controls/`
- `/api/settings/dashboard/`
- `/api/settings/audit-logs/`

Use Settings when you need to enable or disable modules, page links, client access, admin access, developer access, and feature-level permissions.

## 10. Core Workflow

### 10.1 Admin Starts the Workspace

1. Login as Super Admin or Admin.
2. Go to Dashboard.
3. Review project totals, tickets, notifications, and activity.
4. Go to Settings.
5. Confirm system modules are enabled.
6. Confirm role access rules.
7. Add users and assign roles.

### 10.2 Create or Manage a Project

1. Go to Projects.
2. Create or open a project.
3. Add project idea, description, technologies, and features.
4. Assign owner, client, developers, and teams.
5. Configure repository or hosted URL connection.
6. Generate or review project flow.
7. Add tasks and move them through Kanban statuses.
8. Track deployments, documents, tickets, commits, and approvals.

### 10.3 Developer Work Process

1. Login as Developer.
2. Open assigned project.
3. Review backlog, current tasks, blockers, and comments.
4. Upload files or push Git changes where enabled.
5. Update task status.
6. Respond to tickets or correction requests.
7. Watch notifications for admin review, deployment, and client changes.

### 10.4 Client Work Process

1. Login as Client.
2. Open visible projects.
3. Review progress, hosted URL, approved files, and tickets.
4. Raise new tickets with screenshots or details.
5. Track admin responses and approval states.

### 10.5 Settings Control Process

1. Go to Settings.
2. Use Command Center to review platform health, module status, access rules, storage, and realtime sync.
3. Use Module Control to enable or disable major system modules.
4. Use Page Link Control to control navigation availability.
5. Use Full Access Control to define per-role and per-user permissions.
6. Use Security sections for authentication and server file access.
7. Use Hosting and Storage sections for provider and storage controls.
8. Watch Audit Logs after every sensitive change.

## 11. Realtime and Notification Flow

Realtime is served by Django Channels through Daphne.

Primary WebSocket paths:

| WebSocket | Purpose |
| --- | --- |
| `/ws/events/` | General user events |
| `/ws/tickets/` | Ticket list updates |
| `/ws/tickets/<ticket_id>/` | Individual ticket updates |
| `/ws/notifications/` | Notification stream |
| `/ws/server-monitor/` | Server monitor metrics |
| `/ws/api-monitor/` | API monitor stats |
| `/ws/remote-access/` | Remote access dashboard |
| `/ws/remote-agent/<token>/` | Remote device agent |
| `/ws/file-transfer/` | Disk/file transfer updates |
| `/ws/project-intelligence/` | Project intelligence dashboard |
| `/ws/project-agent/` | Project intelligence agent |

For local Vite, `/ws` is proxied to `ws://127.0.0.1:8001`. For production, Nginx proxies `/ws/` to the backend Daphne process.

Production realtime requires:

```env
USE_INMEMORY_CHANNELS=False
REDIS_URL=redis://redis:6379/0
```

Run:

```powershell
daphne -b 0.0.0.0 -p 8000 manage_ai.asgi:application
celery -A manage_ai worker -l info
celery -A manage_ai beat -l info
```

## 12. API Documentation

The backend includes schema and Swagger routes:

```text
http://127.0.0.1:8001/api/v1/schema/
http://127.0.0.1:8001/api/v1/docs/
```

Main API groups:

| API Group | Base Path |
| --- | --- |
| Users | `/api/users/` |
| Teams | `/api/teams/` |
| Projects | `/api/projects/` |
| Tasks | `/api/tasks/` |
| Tickets | `/api/tickets/` |
| Deployments | `/api/deployments/` |
| Notifications | `/api/notifications/` |
| Audit Logs | `/api/audit-logs/` |
| API Logs | `/api/api-logs/` |
| Settings Dashboard | `/api/settings/dashboard/` |
| Settings Modules | `/api/settings/modules/` |
| Settings Access Controls | `/api/settings/access-controls/` |
| Settings Auth | `/api/settings/auth/` |
| Settings Storage | `/api/settings/storage/` |
| Settings File Access | `/api/settings/file-access/` |
| Server Monitor | `/api/server-monitor/...` |
| Hosting | `/api/hosting/...` |
| API Keys | `/api/api-keys/...` |
| Project Intelligence | `/api/project-intelligence/...` |
| UCE Modules | `/api/v1/...` |

Use `Authorization: Bearer <token>` for authenticated requests.

## 13. Testing and Verification

Frontend:

```powershell
cd frontend
npm run build
npm run lint
npm run test
```

Backend:

```powershell
cd backend
.\.venv\Scripts\activate
python manage.py check
python manage.py test
```

Database and migrations:

```powershell
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

Manual verification checklist:

- Login works for Super Admin, Admin, Developer, and Client.
- `/dashboard` loads without API errors.
- `/settings` loads module, access, auth, storage, audit, and realtime panels.
- Toggling a setting creates an audit trail where supported.
- WebSocket features reconnect after refreshing the browser.
- Project detail page loads tasks, approval, files, deployment, hosted link, and team data.
- File upload works for allowed extensions and size limits.
- Notifications arrive without page reload when backend realtime is active.
- Docker build completes for backend and frontend.

## 14. Production Readiness Checklist

Before production:

- Set `DJANGO_DEBUG=False`.
- Use a strong `DJANGO_SECRET_KEY`.
- Set explicit `DJANGO_ALLOWED_HOSTS`.
- Set exact `CORS_ALLOWED_ORIGINS`.
- Enable secure cookies.
- Enable HTTPS and redirect HTTP to HTTPS.
- Use Redis channel layer, not in-memory channels.
- Run Daphne for ASGI/WebSockets.
- Run Celery worker and Celery beat.
- Configure durable database storage.
- Configure backup strategy for database and media.
- Configure provider tokens only for required providers.
- Store secrets outside Git.
- Confirm `backend/.env` is not committed.
- Confirm `frontend/.env` does not expose private secrets.
- Run migrations.
- Run `collectstatic` if serving Django static assets directly.
- Run frontend production build.
- Verify `/api/v1/docs/` is disabled or protected if public API docs are not desired.
- Review audit logs and admin users.
- Rotate demo passwords or remove demo users.

## 15. Docker Production Deployment

The repository includes:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `docker-compose.yml`

The frontend Nginx serves the React build and proxies:

- `/api/` to backend.
- `/media/` to backend.
- `/ws/` to backend WebSockets.

Recommended production adjustment:

1. Change `docker-compose.yml` backend `env_file` from `./backend/.env.example` to `./backend/.env`.
2. Create a real `backend/.env` with production values.
3. Use `DJANGO_DEBUG=False`.
4. Use Redis with `USE_INMEMORY_CHANNELS=False`.
5. Put a public reverse proxy or load balancer in front with HTTPS.

Build and run:

```powershell
docker compose build
docker compose up -d
```

Apply migrations:

```powershell
docker compose exec backend python manage.py migrate
```

Create a production superuser:

```powershell
docker compose exec backend python manage.py createsuperuser
```

View logs:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f redis
```

Restart:

```powershell
docker compose restart backend frontend
```

Stop:

```powershell
docker compose down
```

Do not remove volumes unless you intentionally want to delete persisted data.

## 16. Manual VM Production Deployment

Use this when not deploying with Docker.

### 16.1 Prepare Server

1. Provision a Linux server.
2. Install Python 3.12, Node.js 20, npm, Redis, Nginx, and Git.
3. Clone the repository.
4. Create a system user for the app.
5. Create `backend/.env` with production settings.

### 16.2 Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Run Daphne with a process manager such as systemd:

```bash
daphne -b 127.0.0.1 -p 8000 manage_ai.asgi:application
```

Run Celery worker:

```bash
celery -A manage_ai worker -l info
```

Run Celery beat:

```bash
celery -A manage_ai beat -l info
```

### 16.3 Frontend

```bash
cd frontend
npm ci
npm run build
```

Serve `frontend/dist` through Nginx, or use the included frontend Docker image.

### 16.4 Nginx Reverse Proxy

Minimum proxy behavior:

- Serve React `index.html` for frontend routes.
- Proxy `/api/` to Daphne.
- Proxy `/media/` to Daphne or a media server.
- Proxy `/ws/` to Daphne with WebSocket upgrade headers.
- Set `client_max_body_size 5g` if large server-file uploads are enabled.

Use HTTPS with Certbot, Cloudflare, or your managed load balancer.

## 17. Database Guidance

Local default:

```env
DB_ENGINE=sqlite
DB_NAME=manageai.sqlite3
```

MySQL production option:

```env
DB_ENGINE=mysql
DB_NAME=manageai
DB_USER=manageai
DB_PASSWORD=strong-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Run migrations after database configuration changes:

```powershell
python manage.py migrate
```

Backups:

- Back up the database daily.
- Back up `media/` daily.
- Keep at least one offsite backup.
- Test restore before relying on backups.

## 18. File Upload and Storage

Important backend settings:

```env
DESKTOP_TRANSFER_MAX_FILE_SIZE=5368709120
DESKTOP_TRANSFER_CHUNK_SIZE=2097152
DESKTOP_TRANSFER_ALLOW_ABSOLUTE_PATHS=False
DATA_UPLOAD_MAX_MEMORY_SIZE=5368709120
FILE_UPLOAD_MAX_MEMORY_SIZE=10485760
```

Storage roots default under backend `media`:

- Desktop transfer uploads.
- Desktop transfer temporary chunks.
- Server project storage.
- Remote transfer files.

Production rules:

- Keep absolute paths disabled unless there is a controlled server-storage requirement.
- Limit allowed extensions to real business needs.
- Put media storage on a persistent disk or object storage.
- Scan uploaded files if files come from clients or external users.
- Keep backups separate from live storage.

## 19. AI and Provider Integrations

AI is disabled by default:

```env
AI_ENABLED=False
AI_PROVIDER=local
```

To enable external AI, set the provider and key:

```env
AI_ENABLED=True
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Other supported provider variables exist for Gemini and Anthropic.

Hosting and deployment integrations use variables such as:

- `GITHUB_TOKEN`
- `VERCEL_API_TOKEN`
- `NETLIFY_API_TOKEN`
- `CLOUDFLARE_API_TOKEN`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AZURE_CLIENT_ID`
- `GCP_PROJECT_ID`
- `DIGITALOCEAN_API_TOKEN`
- `RAILWAY_API_TOKEN`
- `RENDER_API_KEY`

Only store real provider tokens in production secret storage.

## 20. Release Process

Use this process for every production change:

1. Pull latest code in staging.
2. Install dependencies.
3. Run backend checks.
4. Run frontend lint/tests/build.
5. Apply migrations in staging.
6. Verify login, dashboard, settings, projects, tickets, hosting, notifications, and realtime.
7. Back up production database and media.
8. Deploy backend.
9. Run migrations.
10. Deploy frontend.
11. Restart Daphne, Celery worker, Celery beat, and Nginx/frontend service.
12. Verify health check.
13. Verify login and key pages.
14. Watch logs for at least 10 minutes.
15. Record release notes and rollback point.

## 21. Rollback Process

If deployment fails:

1. Stop new traffic if using a load balancer.
2. Keep logs from failed backend/frontend containers or services.
3. Revert to the previous image or Git commit.
4. Restore database only if the migration changed data and rollback is required.
5. Restore media only if files were corrupted or deleted.
6. Restart backend, frontend, Redis, Celery, and beat.
7. Confirm login, dashboard, settings, and critical APIs.
8. Document the root cause.

Avoid deleting Docker volumes during rollback unless you have a verified backup and intentionally want to remove data.

## 22. Monitoring and Maintenance

Daily:

- Check server health.
- Check Celery worker and beat.
- Check Redis memory and connection health.
- Check API error logs.
- Review failed deployments and hosting sync alerts.
- Review suspicious auth or access-control changes.

Weekly:

- Review admin users and access rules.
- Rotate provider tokens if required by policy.
- Test backups.
- Check disk usage for media and uploads.
- Check expired or stale hosted projects.

Monthly:

- Update dependencies in staging.
- Run full regression testing.
- Review audit logs.
- Review security settings.
- Review public domain, SSL, and CORS settings.

## 23. Troubleshooting

### Frontend says backend cannot be reached

Check that Django is running on `127.0.0.1:8001` for local Vite:

```powershell
cd backend
.\.venv\Scripts\activate
python manage.py runserver 127.0.0.1:8001
```

Check frontend Vite:

```powershell
cd frontend
npm run dev
```

### Login fails

1. Confirm migrations ran.
2. Run `python manage.py seed_demo`.
3. Confirm backend `/api/auth/login/` is reachable.
4. Check browser devtools network tab.
5. Check backend logs.

### WebSockets do not update

1. Confirm Daphne is used in production.
2. Confirm Redis is running.
3. Confirm `USE_INMEMORY_CHANNELS=False` in production.
4. Confirm `/ws/` is proxied with upgrade headers.
5. Check browser devtools WebSocket panel.

### Settings toggles do not persist

1. Confirm user is Super Admin or Admin.
2. Confirm `/api/settings/modules/` and `/api/settings/access-controls/` return data.
3. Check backend validation error response.
4. Check audit logs.

### File uploads fail

1. Check Nginx `client_max_body_size`.
2. Check backend upload limits.
3. Check allowed file extensions.
4. Check media volume permissions.
5. Check available disk space.

### Docker frontend loads but API fails

1. Confirm backend container is running.
2. Confirm frontend Nginx has `/api/` proxy.
3. Confirm backend allowed hosts and CORS include the production domain.
4. Check `docker compose logs -f frontend`.
5. Check `docker compose logs -f backend`.

## 24. Final Production Acceptance Checklist

Production is ready when all items pass:

- Public domain opens the frontend over HTTPS.
- `/api/auth/login/` works.
- JWT refresh works.
- Dashboard data loads.
- Settings page loads all sections.
- Module enable/disable works.
- Full access control works.
- Page links respect roles and module controls.
- Notifications update in realtime.
- Server monitor updates in realtime.
- API monitor updates in realtime.
- Project creation and project detail workflows work.
- Ticket create/update workflows work.
- File upload and media access work.
- Celery worker is active.
- Celery beat is active.
- Redis is active.
- Database backup exists.
- Media backup exists.
- Demo passwords are removed or changed.
- Admin access list is reviewed.
- Logs show no repeated server errors.

## 25. Related Documentation

Use these existing documents for deeper module-specific details:

- `docs/API_ENDPOINTS.md`
- `docs/SETTINGS_MODULE.md`
- `docs/HOSTING_MANAGER_ADVANCED.md`
- `docs/PROJECT_INTELLIGENCE_PLATFORM.md`
- `docs/PROJECT_HOSTING_DEPLOYMENT_TICKET_MODULE.md`
- `docs/ENTERPRISE_SERVER_MANAGEMENT_PLATFORM.md`
- `docs/REMOTE_ACCESS_SYSTEM.md`
- `docs/REMOTE_ACCESS_LOCAL_STEPS.md`
- `docs/REMOTE_ACCESS_NGROK_STEP_BY_STEP.md`
- `docs/DEPLOY_CENTER_PRODUCTION_AUDIT.md`
- `docs/PRODUCTION_READINESS_REPORT.md`
- `docs/DEPLOYMENT.md`
