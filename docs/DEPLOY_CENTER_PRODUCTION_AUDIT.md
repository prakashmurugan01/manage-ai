# Deploy Center Production Audit

Date: 2026-06-07

## Root Cause Analysis

The Deployment Center failed for three coupled reasons. First, the frontend could start deployment with no real `ProjectUpload.id`, which produced `/api/hosting/uploads/undefined/deploy/` and a 404 before any provider call could start. Second, frontend and backend defaults treated Vercel as an implicit primary target, so recommendation data could become execution state. Third, deployment runs did not persist provider resource identifiers or real metrics/log metadata consistently, so log polling could ask a provider for a missing deployment resource.

## Exact Files Causing Error

- `frontend/src/pages/HostingDeployment.jsx`: built deploy URLs from `activeUpload.id`, allowed recommendation-driven provider state, showed old locked-provider wording, and displayed pending CPU/RAM/Disk/Network placeholders.
- `backend/apps/hosting/models.py`: `DeploymentRun.primary_provider` previously defaulted to Vercel and lacked `provider_deployment_id`, `build_id`, and `metrics`.
- `backend/apps/hosting/views.py`: upload deploy preflight did not create a failed deployment record for blocked attempts and provider validation was incomplete.
- `backend/apps/hosting/tasks.py`: provider routing had Vercel-centric fallbacks and did not persist provider deployment IDs for every adapter path.

## Fixed Code Paths

- Frontend deploy now resolves only a real upload record ID via `getUploadId()` and blocks deployment before calling the API if the upload ID is missing.
- Provider selection is user-only. Recommendations remain visible but cannot set `primary_provider`.
- Backend deployment creation now creates a `DeploymentRun` before preflight failure responses, so the UI always has a deployment record and logs.
- Provider router now routes only to the selected provider with no automatic fallback.
- Deployment runs now store `provider_deployment_id`, `build_id`, `metrics`, and expanded state-machine statuses.

## Provider Router

Real uploaded-package deployment adapters are wired for:

- AWS: S3 static artifact upload, optional CloudFront invalidation, real `s3://bucket/prefix` provider ID.
- Azure: App Service ZIP deployment through Kudu with Entra service-principal token and real Kudu deployment ID.
- GCP: Cloud Storage object upload through Google OAuth/service-account credentials and real `gs://bucket/prefix` provider ID.
- Vercel: Vercel file upload and deployment API, with no fabricated `.vercel.app` fallback.
- Cloudflare: Cloudflare Pages direct upload through non-interactive Wrangler and Pages API deployment lookup.
- Netlify: Netlify ZIP deployment API with site deployment polling.

## Secret Validation

Deployment preflight validates provider credentials and required target resources before queueing:

- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEPLOYMENT_BUCKET` or `AWS_STORAGE_BUCKET_NAME`.
- Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_APP_SERVICE_NAME`.
- GCP: `GCP_PROJECT_ID`, `GCP_STORAGE_BUCKET`, and one of `GCP_ACCESS_TOKEN`, `GCP_SERVICE_ACCOUNT_JSON`, or `GOOGLE_APPLICATION_CREDENTIALS`.
- Vercel: `VERCEL_TOKEN` or `VERCEL_API_TOKEN`.
- Netlify: `NETLIFY_TOKEN` or `NETLIFY_API_TOKEN`, plus `NETLIFY_SITE_ID`.
- Cloudflare: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT_NAME`.

## Logs And Metrics

The deployment detail poll now also polls deployment logs and metrics. Logs come from persisted task logs plus provider APIs where available: Vercel events, Netlify deploy status, Azure Kudu deployment logs, and Cloudflare Pages logs. AWS and GCP static storage deployments expose real upload/task logs because those storage APIs do not emit build logs.

Metrics no longer show fake CPU/RAM/Disk/Network values. The UI shows real health-probe metrics: latency, HTTP status, DNS, and SSL. Compute resource metrics must be added provider-by-provider only where the provider exposes real monitoring APIs for the selected service.

## Database Fixes

- `0011_project_upload_session.py`: resumable upload sessions.
- `0012_deployment_state_machine_provider_ids.py`: deployment state machine, blank primary-provider default, provider deployment ID, build ID, metrics.
- `0013_alter_hostedproject_hosting_platform_and_more.py`: Azure/GCP provider choices.

## Testing Checklist

Validated earlier in this pass before the final provider-adapter/log polling patches:

- `python manage.py makemigrations --check --dry-run`
- `python manage.py check`
- `python manage.py test apps.hosting.tests.DeploymentProviderSelectionTests`
- `npm run build`

Follow-up validation still needed after the last edits because the shell approval cap blocked more command execution:

- Re-run Django checks and targeted hosting tests.
- Re-run frontend production build.
- Exercise a completed upload through selected AWS/Azure/GCP/Vercel/Cloudflare/Netlify paths with real credentials.
- Verify `/api/hosting/deployments/{id}/logs/` and `/metrics/` during and after deployment.

## Final Validation Report

The Vercel lock/default behavior has been removed. Deploy calls now require a real upload ID and explicit selected provider. Missing credentials or target resources fail with exact reasons and a persisted failed deployment record. Provider routing no longer falls back. Real provider adapters are configured for the requested six providers, but production success still depends on valid external credentials, existing provider target resources, CLI availability for Cloudflare Wrangler, and provider-side permissions.
