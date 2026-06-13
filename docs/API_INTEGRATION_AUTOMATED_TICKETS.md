# API Integration And Automated Ticket Creation Guide

Base URL:

```text
Local:      http://localhost:8000/api
Production: https://your-domain.com/api
```

This document explains how an external chatbot, CRM, ERP, webhook service, mobile app, website, or third-party platform can connect to ManageAI with a generated API key and automatically create support tickets from complaints, incidents, errors, warnings, logs, and service failures.

## 1. What The Integration Does

ManageAI supports project-scoped API keys. Each key belongs to one project and can be used by an external system to securely send issue data into the platform.

Typical connected systems:

| System | Example Use |
|---|---|
| Chatbot | Detect complaints in user conversations and create tickets |
| CRM | Send customer complaints, lead failures, payment issues, account problems |
| ERP | Send order, inventory, billing, employee, or workflow failures |
| Webhook provider | Send event notifications from external automation tools |
| External app | Send application errors, warnings, outage reports, and user feedback |

When external data is received, ManageAI can:

1. Authenticate the API key.
2. Verify the key is active, not expired, within rate limit, and allowed by IP rules.
3. Map the request to the API key's project.
4. Record usage logs and monitoring data.
5. Detect whether the request creates a new issue or updates an existing ticket.
6. Create a ticket automatically.
7. Store source system, external ID, API key prefix, event ID, and raw details in ticket metadata.
8. Display the ticket in Tickets, Dashboard, Admin views, and API Integration screens.

## 2. API Key Management

Administrators can generate API keys from the API Integration page.

Navigation:

```text
Sidebar -> API -> API Integration
```

The generated key is shown once. Store it immediately in the external project's environment variables or secret manager.

Supported API key controls:

| Feature | Description |
|---|---|
| Project mapping | Every key is linked to one project. Incoming tickets are created under that project. |
| Role | `viewer`, `editor`, or `admin` controls the intended integration access level. |
| Rate limiting | Each key has a `rate_limit_per_minute`. Exceeded requests return HTTP `429`. |
| Expiration date | Expired keys are rejected. |
| IP whitelist | Optional allowed IP list. Requests from other IPs are rejected. |
| Usage analytics | Requests, latency, error rate, and last-used time are recorded. |
| Security monitoring | Failed responses and unusual traffic can be reviewed in API logs. |
| Regeneration | A key can be regenerated if leaked or rotated. |
| Disable / enable | A key can be toggled without deleting the integration record. |

API key management endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/uce-api-keys/` | List project API keys |
| POST | `/uce-api-keys/` | Generate a new API key |
| PATCH | `/uce-api-keys/{id}/` | Update role, limits, expiry, whitelist, or active state |
| POST | `/uce-api-keys/{id}/regenerate/` | Rotate the secret key |
| POST | `/uce-api-keys/{id}/toggle/` | Enable or disable the key |
| GET | `/uce-api-keys/{id}/details/` | View connected systems, logs, usage, events, and created tickets |
| GET | `/uce-api-key-logs/` | View API usage logs |

Authenticated administrators use JWT for management APIs:

```http
Authorization: Bearer <jwt_access_token>
```

External systems use generated API keys for ingestion:

```http
Authorization: API_KEY <generated_api_key>
```

## 3. Creating An API Key

Example request:

```bash
curl -X POST "http://localhost:8000/api/uce-api-keys/" \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "project": 12,
    "name": "Website Chatbot Production",
    "role": "editor",
    "rate_limit_per_minute": 120,
    "expires_at": "2026-12-31T23:59:59Z",
    "ip_whitelist": ["203.0.113.10"]
  }'
```

Example response:

```json
{
  "id": "4c1c0e30-7137-4f45-9121-759fc2c2f8ad",
  "project": 12,
  "project_name": "E-Commerce CRM",
  "name": "Website Chatbot Production",
  "key_prefix": "a1b2c3d4",
  "role": "editor",
  "rate_limit_per_minute": 120,
  "expires_at": "2026-12-31T23:59:59Z",
  "is_active": true,
  "ip_whitelist": ["203.0.113.10"],
  "last_used_at": null,
  "plaintext_key": "uce_a1b2c3d4...secret...",
  "warning": "Store this key securely. It will not be shown again."
}
```

Important:

- Copy `plaintext_key` immediately.
- Do not paste it into frontend browser code.
- Store it in `.env`, cloud secrets, or server-side environment variables.
- If the key is exposed, regenerate it immediately.

## 4. Pasting The API Key Into Another Project

In the external project, add these values to the backend environment configuration.

Example `.env`:

```env
MANAGEAI_BASE_URL=http://localhost:8000/api
MANAGEAI_API_KEY=uce_a1b2c3d4_your_generated_secret_key
MANAGEAI_SOURCE_PLATFORM=website-chatbot
```

Node.js example:

```js
const MANAGEAI_BASE_URL = process.env.MANAGEAI_BASE_URL;
const MANAGEAI_API_KEY = process.env.MANAGEAI_API_KEY;

async function sendIssueToManageAI(issue) {
  const response = await fetch(`${MANAGEAI_BASE_URL}/external/issues/`, {
    method: "POST",
    headers: {
      "Authorization": `API_KEY ${MANAGEAI_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(issue)
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || data.error || "ManageAI request failed");
  }

  return data;
}
```

Python example:

```python
import os
import requests

MANAGEAI_BASE_URL = os.environ["MANAGEAI_BASE_URL"]
MANAGEAI_API_KEY = os.environ["MANAGEAI_API_KEY"]

def send_issue_to_manageai(issue):
    response = requests.post(
        f"{MANAGEAI_BASE_URL}/external/issues/",
        headers={
            "Authorization": f"API_KEY {MANAGEAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=issue,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
```

## 5. External Issue Ingestion API

Endpoint:

```http
POST /api/external/issues/
Authorization: API_KEY <generated_api_key>
Content-Type: application/json
```

Minimum request:

```json
{
  "title": "Payment failed in checkout",
  "description": "Customer reported payment issue from chatbot.",
  "priority": "HIGH",
  "source_platform": "website-chatbot",
  "external_id": "conv_98765"
}
```

Recommended request:

```json
{
  "type": "complaint",
  "source_platform": "website-chatbot",
  "external_id": "conv_98765",
  "conversation_id": "conv_98765",
  "message_id": "msg_001",
  "title": "Refund not received",
  "description": "User said: Refund not received after order cancellation.",
  "query": "Refund not received",
  "complaint": "Refund not received",
  "issue_category": "payments",
  "error_message": "Refund status is pending for more than 7 days",
  "priority": "HIGH",
  "customer": {
    "name": "Rahul Kumar",
    "email": "rahul@example.com",
    "phone": "+91-9000000000",
    "account_id": "cust_1044"
  },
  "timestamp": "2026-05-30T15:30:00Z",
  "metadata": {
    "order_id": "ORD-1001",
    "page_url": "https://shop.example.com/orders/ORD-1001",
    "browser": "Chrome",
    "country": "IN"
  },
  "logs": [
    {
      "level": "error",
      "message": "Refund gateway timeout",
      "timestamp": "2026-05-30T15:29:50Z"
    }
  ]
}
```

Current accepted aliases:

| Purpose | Accepted Fields |
|---|---|
| Message type | `type`, `event_type` |
| Source | `source_platform`, `source` |
| External reference | `external_id`, `conversation_id`, `message_id` |
| Title | `title`, `issue`, `query` |
| Description | `description`, `details`, `message`, `complaint` |
| Priority | `priority` |
| Existing ticket update | `ticket_id`, `ticket`, `status` |

Priority mapping:

| Incoming Value | Stored Ticket Priority |
|---|---|
| `CRITICAL` | `P1` |
| `HIGH` | `P2` |
| `MEDIUM` | `P3` |
| `LOW` | `P4` |
| `P1`, `P2`, `P3`, `P4` | Stored as provided |

Successful create response:

```json
{
  "success": true,
  "status": "open",
  "data": {
    "ticket_id": "INC-2026-00024",
    "ticket": 45,
    "event": 88,
    "project": 12,
    "source_platform": "website-chatbot"
  }
}
```

## 6. Chatbot Complaint Intelligence Workflow

External chatbot flow:

1. User sends a message.
2. Chatbot checks the message against complaint keywords and issue rules.
3. If an issue is detected, chatbot builds an issue payload.
4. Chatbot sends the payload to `/api/external/issues/`.
5. ManageAI authenticates the API key.
6. ManageAI maps the request to the API key's project.
7. ManageAI creates a ticket automatically.
8. Ticket appears in the Tickets page and dashboard views.
9. Admins and project teams triage, assign, respond, resolve, and close the ticket.

Example complaint keywords:

```js
const complaintKeywords = [
  "complaint",
  "payment issue",
  "payment failed",
  "server error",
  "order failed",
  "refund not received",
  "not working",
  "login failed",
  "app crashed",
  "service down"
];
```

Chatbot detection example:

```js
function detectComplaint(message) {
  const text = message.toLowerCase();
  return complaintKeywords.some((keyword) => text.includes(keyword));
}

function classifyPriority(message) {
  const text = message.toLowerCase();
  if (text.includes("server down") || text.includes("data loss") || text.includes("payment failed")) return "CRITICAL";
  if (text.includes("refund") || text.includes("order failed") || text.includes("login failed")) return "HIGH";
  if (text.includes("slow") || text.includes("warning")) return "MEDIUM";
  return "LOW";
}

async function onChatbotMessage(user, message, conversationId) {
  if (!detectComplaint(message)) return null;

  return sendIssueToManageAI({
    type: "complaint",
    source_platform: "website-chatbot",
    external_id: conversationId,
    conversation_id: conversationId,
    title: message.slice(0, 120),
    description: `Chatbot complaint from ${user.email}: ${message}`,
    query: message,
    priority: classifyPriority(message),
    customer: {
      name: user.name,
      email: user.email,
      account_id: user.id
    },
    timestamp: new Date().toISOString()
  });
}
```

## 7. Fetching Data From External Platforms

Some systems send data by webhook. Others require polling. Both patterns are supported.

Webhook pattern:

1. Configure the third-party system to call your integration backend.
2. Your integration backend validates the third-party webhook signature.
3. Transform the third-party payload into the ManageAI issue format.
4. Send it to `/api/external/issues/` with the ManageAI API key.

Polling pattern:

1. Run a scheduler every 1-5 minutes.
2. Fetch recent errors, complaints, failed jobs, or service events from the external platform.
3. Deduplicate events using `external_id`.
4. Send only new or changed issues to ManageAI.
5. Save the returned `ticket_id` for future updates.

Polling example:

```js
async function syncFailedOrders() {
  const failedOrders = await externalStore.getFailedOrders({ sinceMinutes: 5 });

  for (const order of failedOrders) {
    await sendIssueToManageAI({
      type: "erp_order_failure",
      source_platform: "erp",
      external_id: `order_${order.id}`,
      title: `Order failed: ${order.id}`,
      description: order.errorMessage,
      issue_category: "orders",
      priority: order.paymentCaptured ? "CRITICAL" : "HIGH",
      customer: order.customer,
      metadata: {
        order_id: order.id,
        amount: order.amount,
        status: order.status
      },
      timestamp: order.updatedAt
    });
  }
}
```

## 8. Updating Ticket Status From External Systems

If the external platform later resolves, reopens, or updates the incident, send an update payload.

Update by ManageAI ticket ID:

```bash
curl -X POST "http://localhost:8000/api/external/issues/" \
  -H "Authorization: API_KEY <generated_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "status_update",
    "ticket_id": "INC-2026-00024",
    "status": "resolved",
    "source_platform": "website-chatbot",
    "external_id": "conv_98765"
  }'
```

Update by `external_id`:

```json
{
  "type": "ticket_update",
  "external_id": "conv_98765",
  "status": "in_progress",
  "source_platform": "website-chatbot"
}
```

Supported status aliases:

| Incoming Status | ManageAI Status |
|---|---|
| `open`, `new` | `OPEN` |
| `in_progress`, `progress` | `IN_PROGRESS` |
| `pending` | `PENDING` |
| `resolved` | `RESOLVED` |
| `closed` | `CLOSED` |

Successful update response:

```json
{
  "success": true,
  "status": "resolved",
  "data": {
    "id": 45,
    "ticket_id": "INC-2026-00024",
    "status": "RESOLVED",
    "priority": "P2",
    "source": "SYSTEM"
  }
}
```

## 9. Ticket Lifecycle

Automated ticket lifecycle:

| Stage | Description |
|---|---|
| Detection | External system detects complaint, incident, error, warning, or failed service. |
| Ingestion | External system sends payload to ManageAI using `Authorization: API_KEY <key>`. |
| Validation | ManageAI validates key prefix, hash/encryption match, active state, expiry, IP whitelist, and rate limit. |
| Project mapping | ManageAI maps the request to the API key's project. |
| Event record | ManageAI creates an `external_issue.created` event with raw payload data. |
| Ticket creation | ManageAI creates a ticket with `source=SYSTEM` and `status=OPEN`. |
| Priority assignment | Incoming priority is normalized into `P1`, `P2`, `P3`, or `P4`. |
| Category mapping | External payload can include `issue_category`, `category`, or metadata for triage. |
| Assignment | Admins can manually assign, or workflow rules can auto-assign. |
| Notification | Admins, owners, or assigned users can receive notification records. |
| Status tracking | Status can be changed inside ManageAI or updated by external systems. |
| Escalation | SLA and workflow rules can escalate overdue or critical tickets. |
| Resolution | Ticket moves to `RESOLVED` when the issue is fixed. |
| Closure | Ticket moves to `CLOSED` after confirmation or stale-ticket automation. |

Visible locations:

- Super Admin Dashboard
- Admin Dashboard
- Tickets page
- API Integration page
- API usage logs
- Live ticket WebSocket panels, when enabled

## 10. Webhook Integration

ManageAI ingestion endpoint can be used as the final destination for webhook events, but recommended production architecture is:

```text
Third-party webhook -> Your integration backend -> ManageAI /api/external/issues/
```

Use your backend as a bridge because it can:

- Verify the third-party webhook signature.
- Hide the ManageAI API key from the public internet.
- Normalize different payload formats.
- Deduplicate repeated webhook retries.
- Add project-specific fields and customer metadata.
- Retry failed ManageAI requests safely.

Example webhook bridge:

```js
app.post("/webhooks/payment-gateway", async (req, res) => {
  const event = req.body;

  if (event.type !== "payment.failed") {
    return res.json({ ignored: true });
  }

  const result = await sendIssueToManageAI({
    type: "payment_failed",
    source_platform: "payment-gateway",
    external_id: event.id,
    title: "Payment gateway failure",
    description: event.error?.message || "Payment failed",
    priority: "CRITICAL",
    customer: {
      email: event.customer_email
    },
    metadata: event
  });

  res.json({ success: true, manageai_ticket: result.data.ticket_id });
});
```

## 11. Request Validation Rules

External requests must follow these rules:

- Use HTTPS in production.
- Send `Authorization: API_KEY <generated_api_key>`.
- Send `Content-Type: application/json`.
- Include at least a title-like field: `title`, `issue`, or `query`.
- Include useful detail in `description`, `details`, `message`, or `complaint`.
- Include a stable `external_id` for deduplication and later status updates.
- Include `source_platform` so logs and analytics show where the issue came from.
- Keep payloads concise. Store very large logs in your system and send a URL or summary.

Recommended required fields for reliable automation:

```json
{
  "type": "complaint",
  "source_platform": "chatbot",
  "external_id": "stable-id-from-external-system",
  "title": "Short issue title",
  "description": "Full issue details",
  "priority": "HIGH",
  "timestamp": "2026-05-30T15:30:00Z"
}
```

## 12. Error Handling

Common responses:

| HTTP | Response | Meaning | Fix |
|---|---|---|---|
| `201` | `success: true` | Ticket created | Store returned `ticket_id`. |
| `200` | `success: true` | Ticket updated | Continue normal workflow. |
| `401` | `Invalid API key` or `Invalid Token` | Missing, invalid, expired, disabled, or IP-blocked key | Check key, expiry, active state, whitelist, and header format. |
| `404` | `Ticket could not be found for update` | Update request references unknown ticket or external ID | Send correct `ticket_id` or original `external_id`. |
| `429` | `Rate limit exceeded` | Too many requests for the key | Retry after 60 seconds or increase rate limit. |
| `500` | Server error | Unexpected backend issue | Retry with backoff and check API logs. |

Retry rules:

- Retry `429` after the `Retry-After` header.
- Retry `5xx` with exponential backoff.
- Do not blindly retry `401`; fix credentials first.
- Use `external_id` to avoid duplicate tickets during retries.

Example retry policy:

```text
Attempt 1: immediate
Attempt 2: 5 seconds
Attempt 3: 30 seconds
Attempt 4: 2 minutes
Attempt 5: 10 minutes
```

## 13. Logging, Monitoring, And Audit Tracking

ManageAI automatically records usage for API-key-authenticated requests:

| Field | Description |
|---|---|
| API key | Key used for the request |
| Endpoint | Request path |
| HTTP method | `GET`, `POST`, `PATCH`, etc. |
| IP address | Client IP or forwarded IP |
| Response code | HTTP response status |
| Response time | Request latency in milliseconds |
| Timestamp | Request time |

Where to view:

- API Integration page
- `/api/uce-api-key-logs/`
- `/api/uce-api-keys/{id}/details/`
- API Monitor page
- Dashboard widgets

Events created by external issue ingestion:

| Event Type | Meaning |
|---|---|
| `external_issue.created` | New ticket created from external payload |
| `external_issue.updated` | Existing ticket updated from external payload |

## 14. Security Best Practices

Use these rules for production:

- Store API keys only on servers, not in browser JavaScript or mobile app bundles.
- Use environment variables or a secret manager.
- Use HTTPS only.
- Set expiration dates for all keys.
- Use IP whitelist for fixed server integrations.
- Use low rate limits first, then increase after monitoring traffic.
- Use one API key per external system or environment.
- Regenerate keys after developer turnover, suspected exposure, or vendor change.
- Disable keys immediately when an integration is retired.
- Never log the full API key. Log only key prefix.
- Validate third-party webhook signatures before forwarding data to ManageAI.
- Remove passwords, card data, access tokens, and sensitive personal data from logs before sending.

## 15. Real-World End-To-End Example

Scenario:

A customer chats with an external chatbot and says:

```text
Refund not received for my cancelled order.
```

Complete workflow:

1. Chatbot receives the message.
2. Chatbot keyword detector matches `refund not received`.
3. Chatbot classifies priority as `HIGH`.
4. Chatbot backend sends payload to ManageAI:

```bash
curl -X POST "http://localhost:8000/api/external/issues/" \
  -H "Authorization: API_KEY <generated_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "complaint",
    "source_platform": "website-chatbot",
    "external_id": "conv_98765",
    "title": "Refund not received",
    "description": "Customer says refund not received for cancelled order ORD-1001.",
    "query": "Refund not received for my cancelled order.",
    "issue_category": "payments",
    "priority": "HIGH",
    "customer": {
      "name": "Rahul Kumar",
      "email": "rahul@example.com"
    },
    "metadata": {
      "order_id": "ORD-1001"
    },
    "timestamp": "2026-05-30T15:30:00Z"
  }'
```

5. ManageAI validates the API key.
6. ManageAI maps the request to the API key's project.
7. ManageAI creates an event: `external_issue.created`.
8. ManageAI creates a ticket:

```text
Ticket ID: INC-2026-00024
Status: OPEN
Priority: P2
Source: SYSTEM
Project: E-Commerce CRM
```

9. Admin views the ticket in:

```text
Sidebar -> Tickets
```

10. Support team updates status to `IN_PROGRESS`.
11. External chatbot can notify the customer that support has started.
12. When resolved, external system sends:

```json
{
  "type": "status_update",
  "ticket_id": "INC-2026-00024",
  "status": "resolved",
  "source_platform": "website-chatbot",
  "external_id": "conv_98765"
}
```

13. ManageAI updates the ticket to `RESOLVED`.
14. Ticket can later be closed after confirmation.

## 16. Troubleshooting

Problem: `401 Invalid API key`

- Confirm header is exactly `Authorization: API_KEY <key>`.
- Confirm the key starts with `uce_`.
- Confirm the key is active.
- Confirm it has not expired.
- Confirm request IP is inside `ip_whitelist`, if configured.
- Regenerate the key if it was copied incorrectly.

Problem: `429 Rate limit exceeded`

- Reduce request frequency.
- Batch low-priority events.
- Increase `rate_limit_per_minute` for trusted integrations.
- Add retry with `Retry-After`.

Problem: Duplicate tickets

- Always send a stable `external_id`.
- Store returned `ticket_id` in the external system.
- Use status update payloads for existing incidents.
- Deduplicate webhook retries in your bridge server.

Problem: Ticket created under wrong project

- The API key determines the project.
- Generate a separate key for each project.
- Check the key's `project_name` in API Integration.

Problem: Ticket update returns `404`

- Check `ticket_id` is the ManageAI ticket ID, for example `INC-2026-00024`.
- Or send the same `external_id` used when the ticket was created.
- Confirm the update uses the same project API key as the original create request.

Problem: Chatbot detects too many false complaints

- Tighten keyword matching.
- Add negative keywords.
- Require complaint intent plus a domain word, such as payment, refund, server, login, order, invoice.
- Use confidence scoring before sending to ManageAI.

## 17. Implementation Checklist

Use this checklist for every new integration:

1. Create or select the ManageAI project.
2. Generate a new API key for that project.
3. Set rate limit, expiry date, role, and optional IP whitelist.
4. Store the key in the external backend environment.
5. Build a small function that posts to `/api/external/issues/`.
6. Add event detection rules in the external system.
7. Include `source_platform`, `external_id`, `title`, `description`, `priority`, and timestamp.
8. Test with a sample complaint.
9. Confirm the ticket appears in ManageAI Tickets.
10. Confirm API usage logs are created.
11. Add retry and deduplication.
12. Add status update calls for resolved or closed issues.
13. Monitor logs for `401`, `429`, and `5xx` errors.
14. Rotate keys regularly.

## 18. Quick Reference

Create ticket:

```http
POST /api/external/issues/
Authorization: API_KEY <key>
Content-Type: application/json
```

Create payload:

```json
{
  "type": "complaint",
  "source_platform": "chatbot",
  "external_id": "conv_123",
  "title": "Server error",
  "description": "User reported server error in chatbot.",
  "priority": "CRITICAL"
}
```

Update ticket:

```json
{
  "type": "status_update",
  "ticket_id": "INC-2026-00024",
  "status": "resolved",
  "source_platform": "chatbot",
  "external_id": "conv_123"
}
```

Main screens:

```text
API keys:        Sidebar -> API -> API Integration
Tickets:         Sidebar -> Tickets
API monitor:     Sidebar -> API -> API Monitor
Dashboard:       Sidebar -> Dashboard
```
