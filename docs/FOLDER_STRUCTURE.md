# Full Project Folder Structure

```text
manage ai/
  README.md
  docker-compose.yml
  docs/
    FOLDER_STRUCTURE.md
    PROJECT_FLOW.md
    DATABASE_SCHEMA.md
    API_ENDPOINTS.md
    DEPLOYMENT.md
  backend/
    Dockerfile
    manage.py
    requirements.txt
    .env.example
    manage_ai/
      settings.py
      urls.py
      asgi.py
      wsgi.py
    apps/
      accounts/
        migrations/
        models.py
        serializers.py
        views.py
        admin.py
        management/commands/seed_demo.py
      projects/
        migrations/
        models.py
        serializers.py
        views.py
        services.py
        admin.py
      tasks/
        migrations/
        models.py
        serializers.py
        views.py
        admin.py
      tickets/
        migrations/
        models.py
        serializers.py
        views.py
        admin.py
      deployments/
        migrations/
        models.py
        serializers.py
        views.py
        admin.py
      documents/
        migrations/
        models.py
        serializers.py
        views.py
        admin.py
      notifications/
        migrations/
        models.py
        serializers.py
        views.py
        services.py
        admin.py
      audit/
        migrations/
        models.py
        serializers.py
        views.py
        services.py
        middleware.py
        admin.py
      analytics/
        urls.py
        views.py
      ai/
        migrations/
        models.py
        serializers.py
        views.py
        services.py
        admin.py
      realtime/
        auth.py
        consumers.py
        routing.py
      core/
        permissions.py
        mixins.py
  frontend/
    Dockerfile
    nginx.conf
    package.json
    package-lock.json
    eslint.config.js
    vite.config.js
    tailwind.config.js
    postcss.config.js
    .env.example
    src/
      App.jsx
      main.jsx
      styles.css
      api/
        client.js
        services.js
      context/
        AuthContext.jsx
        ThemeContext.jsx
      realtime/
        socket.js
      constants/
        navigation.js
      utils/
        format.js
        rbac.js
      components/
        dashboard/
        files/
        layout/
        projects/
        rbac/
        tasks/
        ui/
      pages/
        Dashboard.jsx
        Files.jsx
        Logs.jsx
        Login.jsx
        Monitoring.jsx
        NotFound.jsx
        Notifications.jsx
        ProjectDetail.jsx
        Projects.jsx
        Register.jsx
        Tasks.jsx
        Tickets.jsx
        Users.jsx
```

# Backend Layer Map

- Models: each business domain lives in its own Django app under `backend/apps`.
- Serializers: DRF serializers validate API payloads and expose nested read-only user/project details.
- Views: DRF viewsets and API views enforce query scoping and RBAC.
- URLs: `backend/manage_ai/urls.py` registers all API routers; `analytics/urls.py` handles analytics views.
- Authentication: Simple JWT login, refresh, verify, register, and authenticated profile endpoints.
- Database: SQLite only, configured through `DB_NAME` in `backend/.env`.
- Realtime: ASGI + Channels route `ws/events/` with JWT query-token middleware.

# Frontend Layer Map

- Pages: route-level SaaS screens for auth, dashboard, projects, project details, tasks, tickets, files, users, logs, monitoring, and notifications.
- Components: reusable layout, UI, project connection, task, ticket, file, and dashboard modules.
- API integration: Axios client with JWT bearer injection and refresh-token retry.
- RBAC: route guards and navigation filtering via `utils/rbac.js`.
- Advanced features: Kanban drag-and-drop, Day 1/2/3 task progress, AI task suggestions, GitHub branch/commit sync, branch deployment, tickets with screenshots, theme switching, WebSocket client, monitoring/log views.
