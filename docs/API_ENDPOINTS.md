# API Endpoint List

Base URL: `http://localhost:8000/api`

## Authentication System

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| POST | `/auth/register/` | Register developer/client accounts with `approval_status=PENDING` | Public |
| POST | `/auth/login/` | JWT login with email/password | Public |
| POST | `/auth/refresh/` | Rotate refresh token and issue access token | Public |
| POST | `/auth/verify/` | Verify JWT token | Public |
| GET/PATCH | `/auth/me/` | Current user profile | Authenticated |

JWT access tokens are sent as `Authorization: Bearer <token>`.

## Users

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/users/` | List users scoped by role; optional `approval_status=PENDING|APPROVED|REJECTED|SUSPENDED` | Authenticated |
| POST | `/users/` | Create user/admin | Super Admin |
| GET | `/users/{id}/` | User details | Authenticated scoped |
| PATCH/PUT | `/users/{id}/` | Update user or role | Super Admin |
| POST | `/users/{id}/approve/` | Approve a pending/rejected/suspended user and unlock dashboard access | Admin/Super Admin |
| POST | `/users/{id}/reject/` | Reject a user with optional `reason` | Admin/Super Admin |
| POST | `/users/{id}/suspend/` | Suspend a user with optional `reason` | Admin/Super Admin |
| DELETE | `/users/{id}/` | Delete user | Super Admin |

Pending or rejected users can authenticate, but the frontend restricts dashboard routes until an Admin or Super Admin approves them. Suspended users are marked inactive.

## Projects

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/projects/` | List projects with search/filter/order | Role scoped |
| POST | `/projects/` | Create project | Super Admin/Admin |
| GET | `/projects/{id}/` | Project details | Role scoped |
| PATCH/PUT | `/projects/{id}/` | Update project | Super Admin/Admin |
| DELETE | `/projects/{id}/` | Delete project | Super Admin/Admin |
| GET | `/projects/{id}/kanban/` | Project Kanban task feed | Role scoped |
| GET | `/projects/{id}/analytics/` | Project-level analytics | Role scoped |
| GET/POST | `/projects/{id}/project-flow/` | View or generate/update prompt-to-release project flow | Role scoped / Admin write |
| GET/POST | `/projects/{id}/connection/` | View/update local, hosted, or GitHub connection | Role scoped / Admin write |
| GET | `/projects/{id}/branches/` | GitHub branch list | Role scoped |
| GET | `/projects/{id}/commits/` | Stored commit history for selected branch | Role scoped |
| POST | `/projects/{id}/sync-git/` | Sync GitHub commits for a branch | Super Admin/Admin |
| POST | `/projects/{id}/deploy-branch/` | Trigger deployment from selected branch | Super Admin/Admin |
| GET | `/projects/{id}/local-status/` | Check local localhost URL health | Role scoped |

Filters: `search`, `status`, `priority`, `deployment`, `ordering`.

## Tasks

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/tasks/` | List tasks | Role scoped |
| POST | `/tasks/` | Create task | Super Admin/Admin |
| GET | `/tasks/{id}/` | Task details | Role scoped |
| PATCH/PUT | `/tasks/{id}/` | Update task | Admin or assigned developer limited fields |
| DELETE | `/tasks/{id}/` | Delete task | Super Admin/Admin |
| PATCH | `/tasks/{id}/move/` | Move task on Kanban board | Admin or assigned developer |
| GET | `/tasks/my/` | Current user's assigned tasks | Authenticated |
| GET/POST | `/task-comments/` | Task comments | Role scoped |

Filters: `project`, `status`, `assignee`, `priority`, `search`, `ordering`.

## Tickets

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/tickets/` | List tickets scoped by role | Role scoped |
| POST | `/tickets/` | Raise ticket with optional screenshot | Authenticated scoped |
| GET | `/tickets/{id}/` | Ticket details, assignment, responses | Role scoped |
| PATCH/PUT | `/tickets/{id}/` | Update ticket status/assignment | Admin or scoped developer/client |
| POST | `/tickets/{id}/comment/` | Respond to a ticket | Role scoped |
| POST | `/tickets/{id}/attach/` | Add ticket attachments | Role scoped |
| POST | `/tickets/{id}/create-approval/` | Start approval flow from template | Super Admin/Admin |
| GET/POST | `/ticket-comments/` | Ticket comment API | Role scoped |
| GET/POST | `/service-items/` | Manage service catalog items for tickets | Super Admin/Admin |
| GET/POST | `/ticket-sla-policies/` | Manage SLA policies by priority | Super Admin/Admin |
| GET/POST | `/ticket-business-hours/` | Manage SLA business-hours calendars | Super Admin/Admin |
| GET/POST | `/ticket-holidays/` | Manage SLA holiday calendars | Super Admin/Admin |
| GET/POST | `/ticket-workflows/` | Manage ticket workflow templates and ordered actions | Super Admin/Admin |
| GET | `/ticket-workflow-executions/` | View workflow execution logs | Super Admin/Admin |
| GET/POST | `/ticket-approval-templates/` | Manage approval templates and stages | Super Admin/Admin |
| GET/POST | `/ticket-approvals/` | List/create approval requests | Role scoped / Admin write |
| POST | `/ticket-approvals/{id}/approve/` | Approve the current pending approval stage | Approver/Admin |
| POST | `/ticket-approvals/{id}/reject/` | Reject the current pending approval stage | Approver/Admin |
| GET | `/ticket-approval-stages/` | View approval stage details | Role scoped |

Filters: `project`, `status`, `priority`, `type`, `assigned_to`, `assignee`, `category`, `sla_status`, `date_from`, `date_to`, `q`, `ordering`.

Ticket search uses PostgreSQL full-text ranking with `SearchVector(title, description, comments)` when PostgreSQL is active, and falls back to safe `icontains` search on SQLite.

## Deployment Toggle System

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/deployments/` | List deployment controls | Role scoped |
| GET | `/deployments/{id}/` | Deployment state and history | Role scoped |
| POST | `/deployments/{id}/toggle/` | Toggle deployment ON/OFF | Super Admin/Admin |
| PATCH/PUT | `/deployments/{id}/` | Update environment/version/notes | Super Admin/Admin |

## File Upload System

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/documents/` | List files | Role scoped |
| POST | `/documents/` | Upload PDF/document | Super Admin/Admin |
| GET | `/documents/{id}/` | File metadata | Role scoped |
| GET | `/documents/{id}/download/` | Download file | Role scoped |
| PATCH/PUT | `/documents/{id}/` | Update metadata | Super Admin/Admin |
| DELETE | `/documents/{id}/` | Delete file | Super Admin/Admin |

## Disk-To-Disk File Tracking

Base URL: `/api/v1/file-tracking`

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/dashboard/` | Live totals, volume usage, recent transfers, alerts, chart data | Authenticated |
| GET/POST | `/volumes/` | Manage tracked disks, USB drives, and network volumes | Authenticated |
| GET/POST | `/transfers/` | List or record source-to-destination file movement | Authenticated |
| GET | `/transfers/export/?format=csv` | Export transfer logs as CSV | Authenticated |
| GET | `/events/` | File event stream history | Authenticated |
| GET | `/alerts/` | Large, sensitive, or unusual file movement alerts | Authenticated |
| POST | `/alerts/{id}/acknowledge/` | Acknowledge an alert | Authenticated |
| POST | `/alerts/{id}/resolve/` | Resolve an alert | Authenticated |
| GET/POST | `/rules/` | Manage deterministic alert rules | Admin |

CLI:

```bash
python manage.py track_file_transfer --source "C:\Finance\backup.sql" --destination "D:\Archive\backup.sql" --size 2147483648 --process robocopy
```

## Notifications

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/notifications/` | Current user's notifications | Authenticated |
| POST | `/notifications/` | Create notification | Authenticated |
| POST | `/notifications/{id}/mark_read/` | Mark as read | Recipient |
| POST | `/notifications/broadcast/` | Send to multiple users | Super Admin/Admin |

## Audit Logging And API Monitoring

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/audit-logs/` | Business audit trail | Super Admin |
| GET | `/api-logs/` | API request logs | Super Admin |
| GET | `/analytics/performance/` | Latency/error analytics | Authenticated |

## Analytics Dashboard

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/analytics/dashboard/` | Portfolio totals, status charts, velocity, activity | Role scoped |
| GET | `/analytics/performance/?days=7` | API request volume, latency, errors, slowest requests | Authenticated |

## AI Task Suggestions

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| GET | `/task-suggestions/` | List suggestions | Role scoped |
| POST | `/task-suggestions/generate/` | Generate task suggestions from project context | Super Admin/Admin |
| POST | `/task-suggestions/{id}/approve/` | Convert suggestion into task | Super Admin/Admin |
| PATCH | `/task-suggestions/{id}/` | Update suggestion status/details | Super Admin/Admin |

## Realtime WebSocket

| Protocol | Endpoint | Purpose |
|---|---|---|
| WS | `/ws/events/?token=<access_token>` | User-scoped notifications and future project/task events |
| WS | `/ws/tickets/?token=<access_token>` | Organization-scoped ticket list updates |
| WS | `/ws/tickets/{ticket_id}/?token=<access_token>` | Ticket-specific comments, status, assignment, SLA updates |
