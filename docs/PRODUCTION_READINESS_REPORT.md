# Production Readiness Report

## Scope Completed
- Fixed the Hosting Manager enable/disable lifecycle so project state, status, tag, provider links, lifecycle history, project sync, audit events, and notifications move together.
- Added rollback behavior for provider toggle failures. If a provider rejects the action, the API returns an error and the UI restores the previous state.
- Added `disabled` as a first-class hosted project status.
- Fixed realtime notification delivery on the frontend by accepting the backend websocket `new_notification` payload.
- Removed fake uploaded-package deployment success for unsupported providers. Non-Vercel uploaded deployments now fail validation until a real provider adapter is connected.
- Added deployment start/success/failure notifications.

## Root Cause Summary
- Project toggles only changed `HostedProject.link_is_active`, leaving `status`, `tag`, provider links, management project records, and notifications out of sync.
- Frontend notification code listened for `notification_created`, while the websocket consumer sends `new_notification`.
- The deployment worker had a simulated success path for providers without real deployment implementations.

## Database Changes
- Added hosted project status choice: `disabled`.
- Added migration: `backend/apps/hosting/migrations/0009_hostedproject_disabled_status.py`.

## API Changes
- `POST /api/hosting/{id}/toggle_link/` now performs a synchronized lifecycle toggle.
- `POST /api/hosting/external-toggle/` now uses the same synchronized toggle path.
- Uploaded deployment validation now rejects unsupported automated providers instead of creating mock live records.

## UI Changes
- Hosting project cards now show `Disabled` instead of a misleading paused/running state.
- Toggle mutations use optimistic updates with rollback.
- Enable/Disable labels now match the actual hosting lifecycle action.

## Security And Operations Improvements
- Unsupported provider enable/disable operations fail safely instead of pretending to block a live URL.
- Provider errors are returned to the UI so failed actions do not silently drift.
- Deployment actions no longer create fake project records.

## Verified
- `python manage.py test apps.hosting` passed.
- `python manage.py makemigrations --check --dry-run` passed with no model drift.
- `npm run build` passed.
- `npm run lint` passed.
- Frontend dev server verified at `http://127.0.0.1:5175`.

## Remaining Production Blockers
- Several provider credentials are missing in `backend/.env`; Django system checks report missing tokens for DigitalOcean, GoDaddy, Bluehost, SiteGround, BigRock, cPanel, WHM, Plesk, Railway, Render, Firebase, and Supabase.
- Real URL blocking is only available where a real provider control adapter exists. Unsupported providers now fail safely until their provider-specific enable/disable APIs are implemented.
- Bundle size still needs code-splitting; Vite reports a large production chunk warning.
