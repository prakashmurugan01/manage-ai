# ManageAI Internal SaaS Platform

ManageAI is a production-oriented full-stack SaaS platform inspired by ManageEngine. It centralizes project operations, RBAC user management, task tracking, ticketing with screenshot uploads, local/hosted/GitHub project connections, branch deployments, document management, notifications with sound-ready realtime alerts, analytics, audit logging, API monitoring, AI-assisted task suggestions, Kanban workflows, and WebSocket-ready real-time updates.

The dashboard is role-aware:

- Super Admin: platform command center, users, audit logs, API monitoring, governance.
- Admin: project delivery, task assignment, branch deployment control, tickets, documents.
- Developer: assigned work, Day 1/2/3 progress, blockers, tickets, commit activity.
- Client: project progress, approved files, release visibility, ticket raising.

## Stack

- Frontend: React.js, Vite, Tailwind CSS, Framer Motion, Axios
- Backend: Django, Django REST Framework, SQLite/MySQL, JWT authentication
- Realtime-ready: Django Channels with Redis-ready channel layers
- Integrations: GitHub API via `GITHUB_TOKEN` for branches, commits, developer activity, and branch deployment metadata

## Local Quick Start

1. Create environment files:

```bash
copy backend\.env.sqlite.example backend\.env
copy frontend\.env.example frontend\.env
```

2. Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

4. Open `http://localhost:5173`.

Demo users after seeding:

- `super@manageai.local` / `ManageAI@12345`
- `admin@manageai.local` / `ManageAI@12345`
- `dev@manageai.local` / `ManageAI@12345`
- `client@manageai.local` / `ManageAI@12345`

For a fuller Windows local runbook, see [Deployment guide](docs/DEPLOYMENT.md).

## Fresh MySQL Migration

1. Create a MySQL database with `utf8mb4` charset, or start the included Docker MySQL service.

```bash
docker compose up -d mysql redis
```

2. Configure the backend:

```bash
cd backend
copy .env.mysql.example .env
```

Edit `DB_PASSWORD` if you are not using the compose defaults.

3. Run every migration and prepare approved login accounts:

```bash
python manage.py migrate_mysql
```

Use `python manage.py migrate_mysql --seed-demo` when you also want the demo project/tasks/tickets. Newly registered users remain pending by design; approve them from the Users page, or run `python manage.py migrate_mysql --approve-existing-active` during a one-time data import.

## Documentation

- [Complete project guide](docs/PROJECT_GUIDE.md)
- [Folder structure](docs/FOLDER_STRUCTURE.md)
- [Project flow](docs/PROJECT_FLOW.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [API endpoints](docs/API_ENDPOINTS.md)
- [Deployment guide](docs/DEPLOYMENT.md)
# manage-ai
# Universal Connection Engine

This repository now includes a real-time server and hosting management layer built on Django REST Framework, Channels, Celery, Redis, and a React dashboard.

## Local Setup

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
redis-server
python manage.py migrate
python manage.py seed_data
python manage.py runserver 8000
```

Workers:

```bash
cd backend
celery -A manage_ai worker -l info
celery -A manage_ai beat -l info
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Realtime WebSockets:

- `ws://localhost:8000/ws/server-monitor/?token={jwt_token}`
- `ws://localhost:8000/ws/notifications/?token={jwt_token}`
- `ws://localhost:8000/ws/api-monitor/?token={jwt_token}`

Primary API routes:

- `/api/servers/`
- `/api/server-metrics/`
- `/api/disk-mounts/`
- `/api/hosting/`
- `/api/uce-api-keys/`
- `/api/notifications/`
