# Database Schema

The backend uses SQLite with Django ORM migrations. Core tables are normalized by domain and indexed for role-scoped dashboard queries.

## accounts_user

- Extends Django `AbstractUser`.
- Fields: `email`, `username`, `password`, `first_name`, `last_name`, `role`, `department`, `phone`, `avatar`, `last_seen_at`, standard auth flags.
- Roles: `SUPER_ADMIN`, `ADMIN`, `DEVELOPER`, `CLIENT`.
- `email` is unique and is the JWT login identifier.

## projects_project

- Fields: `name`, `slug`, `project_idea`, `description`, `technologies_used`, `features_to_implement`, `project_flow`, `flow_generated_at`, `status`, `priority`, `owner_id`, `client_id`, `start_date`, `due_date`, `progress`, `budget`, `health_score`, `repository_url`, `connection_type`, `connection_status`, `connection_status_message`, `local_url`, `hosted_url`, `github_owner`, `github_repo`, `github_default_branch`, `selected_branch`, latest commit metadata, `tags`, `created_by_id`, timestamps.
- Many-to-many: `admins`, `developers`.
- Indexes: `status + priority`, `slug`.
- Progress and health are recalculated from task state.

## projects_projectcommit

- Fields: `project_id`, `sha`, `branch`, `message`, `author_name`, `author_email`, `author_login`, `committed_at`, `html_url`, timestamps.
- Unique constraint: `project + sha + branch`.
- Used for GitHub commit history and developer activity analytics.

## tasks_task

- Fields: `project_id`, `title`, `description`, `status`, `priority`, `assignee_id`, `reporter_id`, `due_date`, `estimated_hours`, `logged_hours`, `story_points`, `workflow_day`, `day_progress`, `ai_suggested`, `position`, timestamps.
- Statuses: `BACKLOG`, `TODO`, `IN_PROGRESS`, `REVIEW`, `DONE`, `BLOCKED`.
- Indexes: `project + status + position`, `assignee + status`, `priority`.

## tasks_taskcomment

- Fields: `task_id`, `author_id`, `body`, `is_internal`, timestamps.
- Client users only see non-internal comments.

## deployments_deploymentcontrol

- One-to-one with project.
- Fields: `project_id`, `environment`, `is_enabled`, `status`, `version`, `source_branch`, `commit_sha`, `last_deployed_at`, `toggled_by_id`, `notes`, timestamps.
- Toggle creates immutable deployment history records.

## deployments_deploymenthistory

- Fields: `deployment_id`, `is_enabled`, `status`, `version`, `source_branch`, `commit_sha`, `actor_id`, `notes`, timestamps.

## tickets_ticket

- Enterprise ITSM ticket table.
- Fields: `ticket_id`, `type`, `project_id`, `organization_id`, `title`, `description`, `screenshot`, `priority`, `severity`, `impact`, `urgency`, `status`, `category`, `subcategory`, `service_item_id`, `requester_id`, `raised_by_id`, `assigned_to_id`, `assigned_group_id`, `source`, `auto_assigned`, `assignment_reason`, `first_response_at`, `resolved_at`, `closed_at`, `sla_due_at`, `sla_breached`, `sla_paused_at`, `sla_pause_reason`, `parent_ticket_id`, `tags`, `custom_fields`, timestamps.
- Types: `INCIDENT`, `SERVICE_REQUEST`, `PROBLEM`, `CHANGE`, `TASK`.
- Statuses: `NEW`, `ASSIGNED`, `IN_PROGRESS`, `PENDING`, `RESOLVED`, `CLOSED` plus legacy-compatible `OPEN`, `TRIAGED`.
- Priorities: `P1`, `P2`, `P3`, `P4` plus legacy-compatible `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Relationships: self parent/child, self related tickets, `ServiceItem`, `accounts.Team`, requester/assignee users.
- Indexes: `organization + status + priority`, `project + status + priority`, `assigned_to + status`, `requester + status`, `raised_by + status`, `sla_due_at + sla_breached`, `ticket_id`.

## tickets_slapolicy

- Fields: `organization_id`, `name`, `priority`, `first_response_time`, `resolution_time`, `business_hours_only`, `is_active`, timestamps.
- Unique constraint: `organization + name + priority`.
- Used by SLA due-date calculation and breach checks.

## tickets_businesshours / tickets_holiday

- Business hours fields: `organization_id`, `day_of_week`, `start_time`, `end_time`, `timezone`, timestamps.
- Holiday fields: `organization_id`, `name`, `date`, timestamps.
- Used by business-hours-aware SLA calculation.

## tickets_workflowtemplate / tickets_workflowexecution

- Template fields: `organization_id`, `name`, `trigger_type`, `trigger_conditions`, ordered `actions`, `is_active`, timestamps.
- Execution fields: `template_id`, `ticket_id`, `status`, `logs`, `error`, `started_at`, `completed_at`, timestamps.
- Supported action types: `assign_ticket`, `change_status`, `send_notification`, `add_comment`, `create_child_ticket`, `trigger_webhook`, `ai_classify`.

## tickets_approvaltemplate / tickets_approvalrequest / tickets_approvalstage

- Approval templates store ordered JSON `stages`, `approver_type`, and `is_parallel`.
- Approval requests link a ticket to a template and track `PENDING`, `APPROVED`, `REJECTED`, or `CANCELLED`.
- Approval stages track approver user/role, comments, decision actor, and decision timestamp.

## tickets_ticketcomment

- Fields: `ticket_id`, `author_id`, `body`, `is_internal`, `mentions`, `metadata`, timestamps.
- Clients only see non-internal responses.

## tickets_ticketactivity / tickets_ticketattachment / tickets_serviceitem

- Ticket activity fields: `ticket_id`, `action`, `field_changed`, `old_value`, `new_value`, `actor_id`, `metadata`, `timestamp`.
- Ticket attachments can link to a ticket or specific comment and track uploaded user and file size.
- Service items provide a basic service catalog for ticket classification.

## documents_document

- Fields: `project_id`, `uploaded_by_id`, `title`, `description`, `file`, `category`, `visibility`, `version`, `file_size`, `extension`, timestamps.
- Visibility: `INTERNAL`, `CLIENT`, `PUBLIC`.
- Index: `project + visibility`.

## notifications_notification

- Fields: `recipient_id`, `sender_id`, `title`, `message`, `type`, `is_read`, `project_id`, `task_id`, timestamps.
- Index: `recipient + is_read`.

## audit_auditlog

- Fields: `actor_id`, `action`, `entity_type`, `entity_id`, `metadata`, `ip_address`, `user_agent`, `path`, `method`, `created_at`.
- Used for business events: create, update, delete, deployment toggles.

## audit_apirequestlog

- Fields: `user_id`, `path`, `method`, `status_code`, `duration_ms`, `ip_address`, `query_params`, `payload_size`, `response_size`, `view_name`, `created_at`.
- Used by performance analytics and API monitoring.

## ai_tasksuggestion

- Fields: `project_id`, `title`, `description`, `priority`, `story_points`, `confidence`, `rationale`, `status`, `created_by_id`, timestamps.
- Approved suggestions create real tasks with `ai_suggested=True`.
