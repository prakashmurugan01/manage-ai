# Project Hosting, Deployment, Monitoring And Ticket Management Module

This document defines the detailed requirements for a centralized enterprise module that automatically manages project hosting records, deployment tracking, expiry monitoring, notifications, project lifecycle data, and ticket management.

The goal is to provide a fully automated Project Hosting, Deployment, Monitoring, and Ticket Management Engine with minimal manual entry.

## 1. Module Objectives

The platform must provide one connected operating layer for:

- Project management
- Hosting management
- Domain and SSL tracking
- Deployment records
- Uptime and system health monitoring
- Expiry and renewal reminders
- Ticket management
- Developer assignment
- Resolution tracking
- Cost and renewal reporting
- Activity logs and audit history

When a project is hosted or deployed, all relevant information must automatically sync into the Project Management database and become visible in the Project Management section without manual duplicate entry.

## 2. Centralized Project Management Database

When hosting is created or completed, the system must create or update a centralized project record.

Required project fields:

| Field | Description |
|---|---|
| Project name | Official project title |
| Project description | Business or technical description |
| Project type | Website, SaaS, mobile app, CRM, ERP, ecommerce, internal tool, etc. |
| Client information | Client name, company, contact person, email, phone, address |
| Assigned team | Admin, manager, developers, designers, QA, support users |
| Hosting provider | Hostinger, GoDaddy, AWS, DigitalOcean, Render, Netlify, VPS, custom server |
| Hosting package | Shared hosting, VPS, cloud, dedicated, serverless, plan name |
| Server details | IP address, region, OS, CPU, RAM, disk, panel access metadata |
| Domain name | Primary domain and optional aliases |
| SSL information | SSL issuer, start date, expiry date, auto-renew status |
| Deployment date | Latest deployment timestamp |
| Hosting start date | Date hosting became active |
| Hosting expiry date | Hosting subscription expiry |
| Domain expiry date | Domain registration expiry |
| Renewal date | Next expected renewal date |
| Project cost | Development or project delivery cost |
| Hosting cost | Hosting subscription cost |
| Renewal cost | Expected renewal cost |
| Deployment status | Not deployed, queued, deploying, deployed, failed, rolled back |
| System status | Healthy, warning, degraded, down, maintenance |
| Uptime | Current and historical uptime percentage |
| Metadata | Tags, environment, repository, branch, build command, notes |

The database must support historical changes, so updates to hosting, deployment, cost, expiry, and ticket data are stored as lifecycle events or audit records.

## 3. Automatic Project Creation From Hosting

When a hosting process is completed, the system must:

1. Validate the hosting request.
2. Save hosting provider, package, server, domain, SSL, cost, and date metadata.
3. Create a project record if one does not already exist.
4. Link the hosting record to the project.
5. Set project deployment and hosting status.
6. Register a lifecycle event.
7. Notify administrators and assigned users.
8. Display the project in Project Management automatically.

No manual re-entry should be required after hosting completion.

Recommended matching rules:

| Matching Input | Behavior |
|---|---|
| Existing `project_id` supplied | Update that project directly |
| Existing domain found | Link hosting record to the existing project |
| Existing project name and client match | Update existing project |
| No match found | Create a new project record |

## 4. Unified Project Overview Page

Each project must have one professional overview page that shows business, hosting, deployment, ticket, monitoring, and activity information in a single place.

Required sections:

| Section | Required Data |
|---|---|
| Project summary | Name, type, status, description, client, owner |
| Hosting profile | Provider, package, server details, hosting URL, server IP |
| Domain and SSL | Domain, DNS status, SSL issuer, SSL expiry, domain expiry |
| Deployment status | Current deployment state, latest version, branch, environment |
| Dates | Hosting start, deployment date, hosting expiry, domain expiry, renewal date |
| Costs | Project cost, hosting cost, renewal cost, outstanding amount |
| Assigned team | Admin, project manager, developers, QA, support |
| Deployment history | All deployments with logs, timestamps, status, server, branch |
| Active tickets | Open, assigned, in progress, testing, resolved, closed |
| System health | Uptime, current status, recent downtime, latency |
| Recent activities | Hosting, deployment, tickets, notifications, comments, renewals |
| Audit trail | Who changed what and when |

UI capabilities:

- Search by project, client, domain, provider, status, developer, expiry.
- Filter by hosting provider, expiry status, deployment status, ticket status, health.
- Sort by expiry date, renewal date, latest deployment, open tickets, cost.
- Display clear status badges and countdown indicators.
- Show quick actions for renew, deploy, create ticket, assign developer, open logs.

## 5. Hosting And Domain Expiry Monitoring

The system must continuously monitor hosting, domain, and SSL expiry dates.

Countdown labels:

| Condition | Display Label |
|---|---|
| 30 days remaining | `Expires in 30 Days` |
| 15 days remaining | `Expires in 15 Days` |
| 7 days remaining | `Expires in 7 Days` |
| 5 days remaining | `Expires in 5 Days` |
| 3 days remaining | `Expires in 3 Days` |
| 1 day remaining | `Expires Tomorrow` |
| 0 days or past | `Expired` |

Recommended severity:

| Remaining Time | Severity |
|---|---|
| More than 30 days | Healthy |
| 30 to 16 days | Info |
| 15 to 8 days | Warning |
| 7 to 3 days | High |
| Tomorrow | Critical |
| Expired | Expired / blocked |

The countdown must appear on:

- Project cards
- Project list table
- Hosting Manager
- Project details page
- Dashboard widgets
- Notification center

## 6. Smart Notification Engine

The notification engine must send expiry and workflow alerts automatically.

Notification recipients:

- Super Admin
- Admin
- Project manager
- Assigned developers
- Assigned support users
- Client users, when enabled

Notification channels:

- Dashboard alerts
- Notification center
- Email alerts
- System reminders
- Optional realtime WebSocket alerts

Required notification events:

| Trigger | Notification |
|---|---|
| Hosting expires in 30 days | Early renewal reminder |
| Hosting expires in 15 days | Renewal warning |
| Hosting expires in 7 days | High-priority reminder |
| Hosting expires in 5 days | Escalated reminder |
| Hosting expires in 3 days | Critical reminder |
| Hosting expires tomorrow | Urgent reminder |
| Hosting expired | Expired alert |
| Domain expires soon | Domain renewal reminder |
| SSL expires soon | SSL renewal reminder |
| Deployment completed | Deployment success notification |
| Deployment failed | Deployment failure alert |
| Ticket created | Admin notification |
| Ticket assigned | Developer notification |
| Ticket resolved | User and admin notification |
| Ticket escalated | Admin and manager notification |

Each notification must store:

- Recipient
- Project
- Related ticket or deployment, if applicable
- Title
- Message
- Type
- Urgency
- Read/unread status
- Created timestamp

## 7. Automated Deployment Tracking

A dedicated Deployment Center must manage deployment activities.

When deployment completes successfully, the system must automatically:

1. Register a deployment record.
2. Capture deployment date and time.
3. Store deployment logs.
4. Record server and hosting information.
5. Track deployment status.
6. Link deployment to the project.
7. Update latest deployment fields on the project.
8. Create a project activity entry.
9. Notify admins and assigned users.

Deployment record fields:

| Field | Description |
|---|---|
| Project | Linked project |
| Environment | Production, staging, development |
| Provider | Netlify, Render, VPS, AWS, DigitalOcean, custom |
| Branch | Git branch deployed |
| Commit SHA | Source commit identifier |
| Version | Release version or build number |
| Status | Queued, running, success, failed, rolled back |
| Started at | Deployment start timestamp |
| Completed at | Deployment completion timestamp |
| Duration | Total deployment time |
| Logs | Build and server logs |
| Server details | Server, IP, region, hosting package |
| Triggered by | User or automation |
| Rollback link | Previous deployment reference |

Deployment statuses:

```text
QUEUED
RUNNING
SUCCESS
FAILED
ROLLED_BACK
CANCELLED
```

Deployment history must be visible inside:

- Deployment Center
- Project overview page
- Dashboard recent activity
- Audit trail

## 8. Project Detail Synchronization

All related modules must sync back to the project record.

Synchronization sources:

| Source Module | Project Updates |
|---|---|
| Hosting Manager | Provider, domain, SSL, expiry, cost, health |
| Deployment Center | Latest deployment, status, logs, environment |
| Ticket Center | Active ticket counts, critical incidents, latest status |
| Server Monitor | Uptime, latency, CPU, RAM, disk, system status |
| Notifications | Renewal reminders, escalations, user actions |
| API Integration | External issue intake and API-created tickets |

Synchronization rules:

- Project overview must always show the latest linked hosting data.
- Deployment success updates project deployment status to `DEPLOYED`.
- Deployment failure updates project deployment status to `FAILED`.
- Expired hosting updates project health to warning or expired.
- Critical open tickets affect project health score.
- Renewals update expiry and renewal dates.
- Every automatic sync writes an activity log entry.

## 9. Ticket Management System

The platform must include a complete Ticket Center.

Ticket creation sources:

- User-created support ticket
- Admin-created ticket
- Developer bug report
- Chatbot/API-created ticket
- Hosting expiry incident
- Deployment failure
- Server downtime
- Domain or SSL warning

When a user raises a support ticket:

1. Ticket is recorded in Ticket Center.
2. Ticket is linked to the project.
3. Admins receive instant notification.
4. Ticket appears in project active tickets.
5. Admin can assign a developer.
6. Assigned developer receives notification immediately.
7. Ticket activity history starts.

Ticket fields:

| Field | Description |
|---|---|
| Ticket ID | Generated reference, such as `INC-2026-00024` |
| Project | Linked project |
| Title | Short issue title |
| Description | Full issue details |
| Type | Incident, service request, problem, change, task |
| Priority | Critical, high, medium, low or P1-P4 |
| Status | Current lifecycle status |
| Category | Hosting, domain, SSL, deployment, bug, payment, support |
| Requester | User or system source |
| Assigned developer | Developer responsible for resolution |
| Assigned group | Optional team |
| Attachments | Screenshots, logs, documents |
| Resolution notes | Developer fix summary |
| Source | Client, developer, admin, system |
| Metadata | External IDs, API key prefix, logs, source platform |
| Created / updated | Timestamps |

## 10. Developer Assignment Workflow

Admins must be able to assign tickets to developers.

Assignment workflow:

1. Admin opens Ticket Center or project active tickets.
2. Admin selects a developer.
3. System updates `assigned_to`.
4. Ticket status changes to `ASSIGNED`, if currently open.
5. Developer receives notification.
6. Project activity is recorded.
7. Dashboard counts update.

Developer ticket stages:

```text
OPEN
ASSIGNED
IN_PROGRESS
TESTING
RESOLVED
CLOSED
```

Current implementation note:

The existing backend has `OPEN`, `TRIAGED`, `ASSIGNED`, `IN_PROGRESS`, `PENDING`, `RESOLVED`, and `CLOSED`. To support the requested workflow exactly, add `TESTING` as an additional ticket status or map `TESTING` to `PENDING` until the database enum is extended.

Recommended status behavior:

| Status | Meaning |
|---|---|
| Open | Ticket is created and waiting for triage |
| Assigned | Admin assigned a developer |
| In Progress | Developer started work |
| Testing | Fix is being verified |
| Resolved | Developer completed the fix |
| Closed | User/admin confirmed closure |

## 11. Automated Resolution Workflow

When a developer fixes an issue:

1. Developer marks ticket as `RESOLVED`.
2. Developer enters resolution notes.
3. System stores resolution notes permanently.
4. User receives notification with resolution details.
5. Admin receives completion update.
6. Project activity is recorded.
7. Ticket remains available for audit and reporting.
8. Ticket can be closed by admin or requester after confirmation.

Resolution data:

| Field | Description |
|---|---|
| Resolved by | Developer user |
| Resolved at | Timestamp |
| Resolution notes | Fix details |
| Root cause | Optional problem cause |
| Files changed | Optional references |
| Deployment reference | Optional deployment that fixed the issue |
| Testing notes | QA or verification details |
| Closure confirmation | Admin or requester confirmation |

## 12. Cost Monitoring

The system must track project and hosting costs.

Required cost fields:

| Field | Description |
|---|---|
| Project cost | Development/service delivery cost |
| Hosting cost | Current hosting package cost |
| Domain cost | Domain renewal cost |
| SSL cost | SSL certificate cost, if paid |
| Renewal cost | Total upcoming renewal estimate |
| Paid amount | Amount paid by client |
| Pending amount | Outstanding balance |
| Currency | INR, USD, etc. |
| Billing cycle | Monthly, yearly, one-time |

Cost views:

- Project detail cost section
- Hosting Manager cost column
- Dashboard revenue/cost analytics
- Renewal report
- Client/project export

Automation:

- Calculate renewal cost from hosting + domain + SSL.
- Flag projects with upcoming unpaid renewals.
- Notify admins before paid services expire.
- Store cost changes in audit history.

## 13. Activity Logs And Audit Trail

Every important action must create an activity or audit entry.

Events to log:

- Project created from hosting
- Hosting details updated
- Hosting renewed
- Hosting expired
- Domain expiry updated
- SSL expiry updated
- Deployment queued
- Deployment completed
- Deployment failed
- Ticket created
- Ticket assigned
- Ticket status changed
- Ticket resolved
- Ticket closed
- Notification sent
- Cost updated
- API key used for external ticket creation

Each log entry must store:

- Actor user or system
- Action type
- Project
- Related hosting/deployment/ticket record
- Old value and new value, when applicable
- Metadata
- Timestamp

## 14. Role-Based Access Control

Required role behavior:

| Role | Capabilities |
|---|---|
| Super Admin | Full access to all projects, hosting, deployments, tickets, users, costs, and logs |
| Admin | Manage assigned projects, hosting, deployments, tickets, assignment, and renewals |
| Project Manager | View/manage assigned project lifecycle and tickets |
| Developer | View assigned projects and assigned tickets, update progress and resolution |
| Client | View own projects and tickets, create tickets, receive updates |
| Support | Triage and respond to assigned tickets |

Sensitive fields such as hosting credentials, API keys, and server access details must be hidden from unauthorized roles.

## 15. Realtime Dashboard Analytics

Dashboard must show live operational metrics:

- Total projects
- Hosted projects
- Deployed projects
- Projects expiring soon
- Expired projects
- Open tickets
- Critical tickets
- Deployment success/failure counts
- Uptime percentage
- Down servers
- Renewal cost due
- Recent activities
- Notification count

Recommended charts:

- Hosting expiry trend
- Ticket status distribution
- Deployment success rate
- Uptime history
- Cost and renewal forecast
- Active incidents by priority

## 16. Automation Rules

Required automation:

| Automation | Trigger | Result |
|---|---|---|
| Project auto-create | Hosting completed | Create project and link hosting |
| Project auto-sync | Hosting/deployment/ticket update | Update project overview |
| Expiry countdown | Daily scheduler | Update status and countdown label |
| Renewal reminder | 30/15/7/5/3/1/0 days | Send notifications |
| Deployment registration | Deployment success/failure | Store deployment record and logs |
| Ticket notification | Ticket created | Notify admins |
| Developer notification | Ticket assigned | Notify assigned developer |
| Resolution notification | Ticket resolved | Notify requester and admin |
| Escalation | Critical or overdue ticket | Notify admin/manager |
| Cost reminder | Renewal cost due soon | Notify admin/client |
| Audit logging | Any important change | Store activity/audit entry |

## 17. Data Flow

Hosting to project flow:

```text
Hosting completed
-> collect hosting/domain/SSL/server/cost metadata
-> create or update project
-> link hosting record to project
-> calculate expiry countdown
-> create lifecycle event
-> notify users
-> display project in Project Management
```

Deployment to project flow:

```text
Deployment started
-> create deployment record
-> capture logs and status
-> deployment completed or failed
-> update project deployment status
-> append deployment history
-> notify users
-> refresh dashboard analytics
```

Ticket flow:

```text
Ticket raised
-> save ticket
-> notify admin
-> admin assigns developer
-> notify developer
-> developer updates progress
-> developer resolves issue
-> notify user and admin
-> close after confirmation
-> retain full audit history
```

## 18. Page And Navigation Requirements

Required pages:

| Page | Purpose |
|---|---|
| Project Management | List all projects with hosting, expiry, deployment, and ticket indicators |
| Project Detail | Unified project overview and lifecycle dashboard |
| Hosting Manager | Manage hosting records, domains, SSL, renewals, uptime |
| Deployment Center | Trigger and track deployments |
| Ticket Center | Create, assign, resolve, and audit support tickets |
| Notification Center | View reminders, alerts, assignment updates, and expiry warnings |
| Dashboard | Executive summary of project, hosting, deployment, and ticket health |
| Audit Logs | Enterprise history of important operations |

Required navigation entries:

- Dashboard
- Projects
- Hosting Manager
- Deployment Center
- Tickets
- Notifications
- API Integration
- Monitoring
- Settings

## 19. Acceptance Criteria

The module is complete when:

1. Hosting completion automatically creates or updates a project.
2. Project Management shows hosted projects without manual entry.
3. Project detail page displays hosting, deployment, domain, SSL, cost, tickets, team, uptime, and activity data.
4. Project cards show expiry countdown labels.
5. Notifications are sent at 30, 15, 7, 5, 3, 1, and 0 day thresholds.
6. Deployment Center stores deployment records and logs.
7. Deployment records sync into project history.
8. Tickets can be created, assigned, progressed, resolved, and closed.
9. Developers receive assignment notifications.
10. Users and admins receive resolution notifications.
11. All important actions are logged.
12. Role-based access controls protect sensitive data.
13. Dashboard analytics update from hosting, deployment, monitoring, and ticket data.
14. API-created tickets and system-created tickets appear in the same Ticket Center.

## 20. Recommended Implementation Phases

Phase 1: Data Foundation

- Extend project, hosting, deployment, ticket, notification, and activity models as needed.
- Add project-hosting-deployment relationships.
- Add expiry countdown utilities.

Phase 2: Hosting Automation

- Auto-create/update projects from hosting completion.
- Add expiry scheduler and notifications.
- Add cost and renewal fields.

Phase 3: Deployment Center

- Register deployment records.
- Store logs and deployment history.
- Sync latest deployment status to project detail.

Phase 4: Ticket Workflow

- Add `TESTING` status or map it to existing status.
- Add resolution notes.
- Improve developer assignment notifications.
- Add project ticket summaries.

Phase 5: Unified UI

- Build or enhance project overview page.
- Add filters, sorting, and status badges.
- Add dashboard analytics and activity streams.

Phase 6: Enterprise Automation

- Add escalation rules.
- Add audit reporting.
- Add email templates.
- Add realtime updates.

## 21. Key Backend Objects

Recommended object model:

```text
Project
  -> HostingRecord / HostedProject
  -> DeploymentRecord
  -> Ticket
  -> Notification
  -> ActivityLog
  -> AuditLog
  -> CostRecord / RenewalRecord
```

Important relationships:

- One project can have multiple hosting records over time.
- One project can have multiple deployment records.
- One project can have many tickets.
- One ticket can have many comments, attachments, and activity records.
- One project can have many notifications and audit entries.

## 22. Operational Summary

This module should behave as a centralized lifecycle engine:

```text
Host -> Auto-create project -> Monitor expiry -> Notify users
Deploy -> Store logs -> Sync project status -> Show history
Ticket -> Assign developer -> Track progress -> Resolve -> Audit
Monitor -> Detect health issues -> Alert -> Create incidents
Costs -> Track renewals -> Notify before payment/expiry
```

The final experience should feel like an enterprise control center where project owners, admins, developers, and clients can see every important project, hosting, deployment, ticket, and renewal detail from one connected system.
