# Step-by-Step Local Dial-In

These commands assume the project root is `D:\projects\manage ai` and the shell is Windows PowerShell.

## 1. Backend Environment

Create and activate the backend virtual environment:

```bash
cd "D:\projects\manage ai"
cd backend
copy .env.sqlite.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

This project is configured for SQLite only. No external database server is required.

For private GitHub repositories, set `GITHUB_TOKEN` in `backend\.env`. Public repository branch and commit sync can work without a token, but production should use one to avoid rate limits.

## 2. Optional: Start Redis

Redis is optional and only used for production-grade WebSocket fanout. The local SQLite env uses `USE_INMEMORY_CHANNELS=True`, so the API and frontend run without Redis.

If you want Redis-backed WebSockets locally:

```bash
cd "D:\projects\manage ai"
docker compose up -d redis
```

## 3. Create Schema And Demo Data

```bash
cd "D:\projects\manage ai\backend"
.venv\Scripts\activate
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo
```

## 4. Run Backend

```bash
cd "D:\projects\manage ai\backend"
.venv\Scripts\activate
python manage.py runserver 8000
```

For ASGI and WebSocket-ready local mode:

```bash
cd "D:\projects\manage ai\backend"
.venv\Scripts\activate
daphne -b 0.0.0.0 -p 8000 manage_ai.asgi:application
```

Backend URL:

```text
http://localhost:8000/api
```

## 5. Run Frontend

Open a second PowerShell terminal:

```bash
cd "D:\projects\manage ai"
cd frontend
copy .env.example .env
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## 6. Demo Role Logins

Use these seeded accounts after `python manage.py seed_demo`:

| Role | Email | Password |
|---|---|---|
| Super Admin | `super@manageai.local` | `ManageAI@12345` |
| Admin | `admin@manageai.local` | `ManageAI@12345` |
| Developer | `dev@manageai.local` | `ManageAI@12345` |
| Client | `client@manageai.local` | `ManageAI@12345` |

Each role opens a different dashboard experience:

- Super Admin: system control, users, logs, API monitoring, audit activity.
- Admin: projects, task delivery, branch deployments, tickets, documents.
- Developer: assigned work, Day 1/2/3 progress, review queue, tickets.
- Client: project progress, approved files, release visibility, ticket raising.

## 7. Reset Local SQLite Data

To start fresh, stop the backend, delete `backend\validation.sqlite3`, then run migrations and seed again.

```bash
cd "D:\projects\manage ai\backend"
.venv\Scripts\activate
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

Then run the frontend in a second terminal:

```bash
cd "D:\projects\manage ai\frontend"
npm run dev
```

## 8. Validation Commands

Backend:

```bash
cd "D:\projects\manage ai\backend"
.venv\Scripts\activate
python manage.py check
python manage.py makemigrations accounts projects tasks tickets deployments documents notifications audit ai --check --dry-run
```

Frontend:

```bash
cd "D:\projects\manage ai\frontend"
npm run lint
npm run build
```

# Deployment-Ready Guide

## Environment Variables

Backend production values:

- `DJANGO_SECRET_KEY`: long random secret.
- `DJANGO_DEBUG=False`.
- `DJANGO_ALLOWED_HOSTS`: production domains.
- `CORS_ALLOWED_ORIGINS`: production frontend URL.
- `DB_NAME`: SQLite file path relative to `backend/`, for example `data/manageai.sqlite3`.
- `REDIS_URL`: Redis instance for Channels.
- `ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`.
- `GITHUB_TOKEN`: token used for GitHub API repository, branch, and commit sync.

Frontend production values:

- `VITE_API_BASE_URL=https://api.example.com/api`
- `VITE_WS_URL=wss://api.example.com/ws/events/`

## Docker

Build and run the complete platform:

```bash
docker compose up --build
```

Run migrations inside the backend container:

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

## Production Hardening Checklist

- Set `DJANGO_DEBUG=False`.
- Back up the SQLite database file regularly, or mount it to durable storage in Docker.
- Use managed Redis or a secured Redis cluster for Channels.
- Serve Django through Daphne or a process manager behind Nginx.
- Terminate TLS at the load balancer or Nginx.
- Store media files in object storage for multi-instance deployments.
- Add rate limiting at the reverse proxy or API gateway.
- Rotate JWT signing secret through a controlled maintenance process.
- Send structured logs to a central logging platform.
- Run `python manage.py check --deploy` before release.
- Run frontend `npm run build` and serve `/dist` via Nginx/CDN.

## RBAC Deployment Notes

- Super Admin has full user, analytics, logs, and system control.
- Admin manages projects, tasks, tickets, files, branch deployments, notifications.
- Developer sees assigned/project tasks, updates progress/status, and handles assigned tickets.
- Client sees project progress, permitted files, deployment state, and can raise tickets.
