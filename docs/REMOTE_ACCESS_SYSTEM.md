# ManageAI Remote Access System

## Purpose

The Remote Access Command Center provides AnyDesk-style laptop-to-laptop access through ManageAI. Browsers never read a local disk directly. A lightweight desktop agent runs on the target machine, connects outbound to ManageAI over WebSocket, and only exposes screen, control, and disk actions after the target user manually approves a session.

## Current Architecture

- **Web dashboard:** `frontend/src/pages/RemoteAccess.jsx`
  - Registers target devices.
  - Displays generated connection tokens and shareable URLs.
  - Lets client, developer, admin, or super admin users request access with a token.
  - Shows live sessions, device status, disk explorer results, and activity logs.

- **REST API:** `backend/apps/remote_access/views.py`
  - `POST /api/remote-devices/` creates a device and automatically generates a secure token.
  - `POST /api/remote-devices/connect-token/` accepts a raw token or a URL containing `?token=...`.
  - `POST /api/remote-devices/{id}/request-session/` requests access to a known device.
  - `POST /api/remote-sessions/{id}/command/` sends approved mouse/keyboard commands.
  - `POST /api/remote-sessions/{id}/files/` sends approved disk commands.

- **Realtime layer:** Django Channels in `backend/apps/remote_access/consumers.py`
  - `/ws/remote-agent/<token>/` is used by the desktop agent.
  - `/ws/remote-access/` is used by the dashboard.
  - Session requests, approvals, frames, file results, and transfer events are relayed through server-side channel groups.

- **Desktop agent:** `backend/agents/remote_agent.py`
  - Runs on the target laptop.
  - Connects outbound using the generated token.
  - Sends heartbeat/capability metadata.
  - Prompts the target user to type `YES` before access is granted.
  - Streams screen frames and executes file/control commands for approved sessions.

## Connection Flow

1. **Generate token**
   - Admin/developer/client opens Remote Access.
   - Clicks **Register Agent**.
   - The backend creates a `RemoteDevice` and automatically generates a cryptographically random token.

2. **Start target agent**
   - On the target laptop:
     ```bash
     pip install websockets mss pillow pyautogui
     python agents/remote_agent.py --server ws://127.0.0.1:8001 --token GENERATED_TOKEN
     ```
   - The agent connects to `/ws/remote-agent/<token>/`.
   - The dashboard shows the device as online.

3. **Request connection**
   - The operator can use either:
     - Raw token in **Connect By Token**.
     - URL form: `http://127.0.0.1:5175/remote-access?token=GENERATED_TOKEN`.
   - The backend creates a `RemoteSession` with status `REQUESTED`.
   - The request is pushed to the agent over WebSocket.

4. **Manual approval**
   - The target laptop shows an approval prompt in the agent terminal.
   - If the target user types `YES`, the agent sends `session.approved`.
   - The backend marks the session `ACTIVE`.
   - The admin/client dashboard receives the realtime update and grants access automatically.

5. **Remote desktop and disk access**
   - View/control permissions decide what the requester can do:
     - `VIEW`: live screen only.
     - `CONTROL`: screen plus mouse/keyboard.
     - `FILES`: disk browsing and transfer commands.
     - `ADMIN`: full desktop plus disk access.
   - Disk commands are sent to the agent. Results are returned over WebSocket.

6. **Disconnect**
   - Either side can disconnect.
   - The session is marked `ENDED`.
   - Activity is logged.

## Localhost Runbook

1. Apply migrations:
   ```bash
   cd backend
   python manage.py migrate
   ```

2. Start backend:
   ```bash
   python manage.py runserver 127.0.0.1:8001
   ```

3. Start frontend with a clean Windows-safe environment variable:
   ```bash
   cd frontend
   set "VITE_API_BASE_URL=http://localhost:8001/api" && npm run dev -- --host 127.0.0.1 --port 5175
   ```

4. Open:
   ```text
   http://127.0.0.1:5175/remote-access
   ```

5. Register a device, copy the generated command, and run it on the target laptop.

## Security Model

- Tokens are generated server-side with `secrets.token_urlsafe`.
- The agent connects outbound; browsers do not directly access local devices or disks.
- A valid token can only create a request. It does not grant access by itself.
- The target agent must manually approve the request.
- Permissions are stored per session.
- Full control and full desktop/disk modes are limited by role checks.
- All session starts, approvals, denials, disconnects, file actions, and control actions are logged.

## Production/Cloud Plan

1. **Transport security**
   - Use HTTPS and WSS only.
   - Terminate TLS at a trusted load balancer or reverse proxy.
   - Configure strict CORS and allowed hosts.

2. **Token hardening**
   - Store hashed device tokens instead of plain tokens.
   - Add token rotation and expiration.
   - Add short-lived one-time connection codes for support sessions.

3. **End-to-end encryption**
   - Use WebRTC DataChannels/media with DTLS/SRTP for screen/control traffic.
   - Use per-session ephemeral keys.
   - Keep the server as a signaling and audit layer where possible.

4. **Agent hardening**
   - Package the agent as a signed Windows/macOS/Linux service.
   - Add a native approval dialog instead of terminal input.
   - Add OS permission checks for screen recording and input control.
   - Add allow/deny lists for disk paths.

5. **File transfer**
   - Move from prototype frame relay to resumable chunk transfer.
   - Add checksum verification.
   - Add malware scanning hooks for uploaded files.

6. **Scale**
   - Use Redis channel layer in production.
   - Run Daphne/Uvicorn workers behind a load balancer.
   - Store activity logs in durable database storage.
   - Add metrics for online agents, sessions, bandwidth, transfer failures, and approval latency.

7. **Access control**
   - Enforce company/tenant boundaries.
   - Add per-user remote access policies.
   - Add audit export and retention policies.

## Implementation Plan

1. Stabilize local token connection and approval flow.
2. Replace terminal approval with a desktop-native approval popup.
3. Add true WebRTC screen streaming for lower latency.
4. Add resumable upload/download with chunk metadata persisted in `RemoteTransfer`.
5. Add device-to-device transfer orchestration through server-approved sessions.
6. Add production token hashing, rotation, and expiration.
7. Add cloud deployment profile with TLS, Redis Channels, monitoring, rate limiting, and tenant policy enforcement.
