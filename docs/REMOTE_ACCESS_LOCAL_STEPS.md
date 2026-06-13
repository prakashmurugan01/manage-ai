# Remote Access Local Test Steps

Use this checklist when the Remote Access page shows devices as `OFFLINE` or the connection does not start.

## 1. Start Backend

From the project root:

```bash
cd backend
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Keep this terminal open.

## 2. Start Frontend

From a second terminal:

```bash
cd frontend
set "VITE_API_BASE_URL=http://localhost:8000/api" && npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/remote-access
```

## 3. Register Or Use Existing Device

If no device exists:

1. Click **Register Agent**.
2. Enter a device name.
3. Click **Create secure token**.
4. Copy the generated **Agent command**.

If a device already exists but is `OFFLINE`:

1. Open its device card.
2. Copy **Agent cmd**.
3. Run that command on the target laptop.

## 4. Install Agent Dependencies

On the target laptop:

```bash
pip install websockets mss pillow pyautogui
```

## 5. Run Agent

Run the copied command. It looks like:

If your terminal is inside `D:\projects\manage ai\backend`:

```bash
python agents\remote_agent.py --server ws://localhost:8000 --token GENERATED_TOKEN
```

If your terminal is inside the project root `D:\projects\manage ai`:

```bash
python backend\agents\remote_agent.py --server ws://localhost:8000 --token GENERATED_TOKEN
```

Expected result:

- The terminal stays running.
- The dashboard changes the device from `OFFLINE` to `ONLINE`.

If it stays `OFFLINE`, check:

- Backend is running on the same port used in the command.
- Token was copied exactly.
- Firewall is not blocking localhost/WebSocket.
- You are using the correct path for your current folder:
  - From `backend`: `python agents\remote_agent.py ...`
  - From project root: `python backend\agents\remote_agent.py ...`

## 6. Request Connection

In the dashboard:

1. Select the online device.
2. Choose permission:
   - `View only`
   - `Full control`
   - `File access`
   - `Desktop + disk`
3. Click **Connect**.

Alternative:

1. Copy **Client URL** from the device card.
2. Open it in another browser/user session.
3. Click **Send Approval Request**.

## 7. Approve On Target Laptop

The agent terminal shows:

```text
Remote request: ...
Approve this session? Type YES to approve:
```

Type:

```text
YES
```

Expected result:

- Session becomes `ACTIVE`.
- Remote Desktop panel starts receiving frames.
- Disk Explorer works if the session permission is `File access` or `Desktop + disk`.

## 8. Disk Access

For disk access:

1. Start a session with `File access` or `Desktop + disk`.
2. Approve it on the target laptop.
3. Click the disk button in **Disk Explorer**.
4. Open `C:\`, `D:\`, or another listed drive.

## 9. Common Problems

### Device stays OFFLINE

The desktop agent is not connected. Copy **Agent cmd** from the device card and run it.

### Connect button is disabled

The target device is offline. Start the agent first.

### No remote frames

Install `mss` and `pillow`, then restart the agent:

```bash
pip install mss pillow
```

### Mouse/keyboard does not work

Use `Full control` or `Desktop + disk` permission and install:

```bash
pip install pyautogui
```

### Disk explorer says permission required

The session was started with `View only` or `Full control`. Start a new session with `File access` or `Desktop + disk`.

### Duplicate offline devices

Use the **Delete** button on the offline device card, then register one clean device and run its agent command.

## 10. Local Success Checklist

- Backend terminal is running.
- Frontend terminal is running.
- Agent terminal is running.
- Device status is `ONLINE`.
- Connection request is approved with `YES`.
- Session status is `ACTIVE`.
- Screen frames appear.
- Disk Explorer loads drives for file-access sessions.
