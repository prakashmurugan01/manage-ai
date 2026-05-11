# Project Flow

Project Flow turns a project prompt, idea, technology list, and feature list into a visible delivery path on the project detail page.

## Flow Stages

1. Discovery & Scope
2. Architecture & Data Model
3. Module Build
4. Validation & Hardening
5. Release & Operate

Each stage is stored in `projects_project.project_flow` as JSON with:

- `key`
- `title`
- `phase`
- `status`
- `owner_role`
- `outcome`
- `activities`
- `inputs`
- `outputs`

## API

- `GET /api/projects/{id}/project-flow/` returns the current flow.
- `POST /api/projects/{id}/project-flow/` generates a deterministic flow from the project prompt fields, or stores a supplied custom `flow` array.

Only Admin and Super Admin users can update the flow. All project roles that can view the project can read it.
