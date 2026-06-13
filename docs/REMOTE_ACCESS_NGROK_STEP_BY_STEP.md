# Remote Access With ngrok: Best Step-by-Step Guide

Use this guide when you want to connect a target laptop from another Wi-Fi/network to your local Django backend for temporary testing.

This setup is for testing only. For production, use proper cloud hosting with HTTPS/WSS, authentication hardening, logs, and stable domain configuration.

## What You Need

- Main laptop: runs Django backend, frontend dashboard, and ngrok.
- Target laptop: runs the remote agent.
- A registered device token from the Remote Access dashboard.
- Python installed on both laptops.
- ngrok installed and logged in on the main laptop.

## Important URLs

Your project has these WebSocket routes:

```text
/ws/remote-access/
/ws/remote-agent/<token>/
```

The agent command should use only the server base URL plus `--token`.

Correct:

```powershell
python agents\remote_agent.py --server wss://YOUR-NGROK-URL.ngrok-free.app --token YOUR_DEVICE_TOKEN
```

Do not pass the full `/ws/remote-agent/...` path to `--server`, because the script adds that path automatically.

## 1. Start Django Backend On Main Laptop

Open PowerShell:

```powershell
cd "D:\projects\manage ai (4)\manage ai\backend"
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

Keep this terminal open.

Expected result:

```text
Starting development server at http://0.0.0.0:8001/
```

## 2. Start ngrok On Main Laptop

Open a second PowerShell terminal:

```powershell
ngrok http 8001
```

If Windows says `ngrok is not recognized`, install it first:

```powershell
winget install ngrok.ngrok
```

If ngrok says your agent version is too old, download the latest official Windows binary:

```powershell
New-Item -ItemType Directory -Force -Path C:\tmp\ngrok
Invoke-WebRequest -Uri https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip -OutFile C:\tmp\ngrok\ngrok.zip
Expand-Archive -Path C:\tmp\ngrok\ngrok.zip -DestinationPath C:\tmp\ngrok -Force
C:\tmp\ngrok\ngrok.exe version
```

Then start ngrok with:

```powershell
C:\tmp\ngrok\ngrok.exe http 8001
```

ngrok will show a forwarding URL like:

```text
https://abc123.ngrok-free.app
```

For the remote agent, convert it to WebSocket secure format:

```text
wss://abc123.ngrok-free.app
```

Keep ngrok running.

## 3. Start Frontend Dashboard On Main Laptop

Open a third PowerShell terminal:

```powershell
cd "D:\projects\manage ai (4)\manage ai\frontend"
npm run dev -- --host 0.0.0.0 --port 5173
```

Open the dashboard:

```text
http://localhost:5173/remote-access
```

## 4. Register Or Select A Device

In the Remote Access page:

1. Click **Register Agent** if you need a new device.
2. Enter a clear device name, for example `Office Laptop` or `Test Laptop`.
3. Click **Create secure token**.
4. Copy the generated device token.

If the device already exists:

1. Open the device card.
2. Copy its agent token or generated agent command.

## 5. Prepare The Target Laptop

On the target laptop, install the desktop agent dependencies:

```powershell
pip install websockets mss pillow pyautogui
```

These packages are used for:

- `websockets`: connection to Django.
- `mss` and `pillow`: screen capture.
- `pyautogui`: mouse and keyboard control.

## 6. Copy The Agent Script To Target Laptop

The agent script is here on the main laptop:

```text
D:\projects\manage ai (4)\manage ai\backend\agents\remote_agent.py
```

Copy `remote_agent.py` to the target laptop.

Example target location:

```text
C:\ManageAI\remote_agent.py
```

Then open PowerShell on the target laptop:

```powershell
cd C:\ManageAI
```

## 7. Run The Agent On Target Laptop Using ngrok

Use your ngrok URL and device token:

```powershell
python remote_agent.py --server wss://abc123.ngrok-free.app --token YOUR_DEVICE_TOKEN
```

Replace:

- `abc123.ngrok-free.app` with your actual ngrok domain.
- `YOUR_DEVICE_TOKEN` with the token from the dashboard.

Expected result:

- The terminal stays running.
- The dashboard changes the device status from `OFFLINE` to `ONLINE`.

## 8. Request Remote Access From Dashboard

On the main laptop dashboard:

1. Open `http://localhost:5173/remote-access`.
2. Select the online target device.
3. Choose permission:
   - `View only`
   - `Full control`
   - `File access`
   - `Desktop + disk`
4. Click **Connect**.

## 9. Approve On Target Laptop

The target laptop terminal will show:

```text
Remote request: ...
Approve this session? Type YES to approve:
```

The target user must type exactly:

```text
YES
```

After approval:

- Session becomes `ACTIVE`.
- Screen frames should appear in the dashboard.
- Mouse/keyboard works if permission allows control.
- Disk explorer works if permission allows file access.

## 10. Same Wi-Fi Alternative Without ngrok

Use this only when both laptops are on the same Wi-Fi.

On the main laptop, find the LAN IP:

```powershell
ipconfig
```

Look for IPv4 Address, for example:

```text
192.168.1.10
```

Start Django:

```powershell
cd "D:\projects\manage ai (4)\manage ai\backend"
.\.venv\Scripts\Activate.ps1
python manage.py runserver 0.0.0.0:8001
```

On the target laptop:

```powershell
python remote_agent.py --server ws://192.168.1.10:8001 --token YOUR_DEVICE_TOKEN
```

If it does not connect, allow inbound TCP port `8001` in Windows Firewall on the main laptop.

## 11. Windows Firewall Check

If the target laptop cannot connect to the main laptop on local Wi-Fi:

1. Open **Windows Defender Firewall**.
2. Click **Advanced settings**.
3. Click **Inbound Rules**.
4. Add a new rule.
5. Select **Port**.
6. Select **TCP**.
7. Enter port:

```text
8001
```

8. Allow the connection.
9. Apply to private networks.
10. Name it `ManageAI Django 8001`.

For ngrok, this usually is not needed because the target laptop connects outward to ngrok.

## 12. Common Problems

### Device Stays OFFLINE

Check:

- Django backend is running on port `8001`.
- ngrok is still running.
- The agent uses `wss://...`, not `https://...`.
- The token is copied exactly.
- The agent command uses only the base server URL, not the full WebSocket path.

Correct:

```powershell
python remote_agent.py --server wss://abc123.ngrok-free.app --token YOUR_DEVICE_TOKEN
```

Wrong:

```powershell
python remote_agent.py --server wss://abc123.ngrok-free.app/ws/remote-agent/YOUR_DEVICE_TOKEN/
```

### ngrok URL Changed

Free ngrok URLs can change each time you restart ngrok.

If it changes:

1. Copy the new ngrok HTTPS URL.
2. Convert `https://` to `wss://`.
3. Restart the target laptop agent with the new URL.

### No Screen Frames

Install or reinstall:

```powershell
pip install mss pillow
```

Then restart the agent.

### Mouse Or Keyboard Does Not Work

Install:

```powershell
pip install pyautogui
```

Then start a session with:

```text
Full control
```

or:

```text
Desktop + disk
```

### Disk Access Not Working

Start a new session with:

```text
File access
```

or:

```text
Desktop + disk
```

View-only sessions cannot use disk explorer.

## 13. Best Testing Checklist

- Django backend is running at `0.0.0.0:8001`.
- ngrok is forwarding to `http://localhost:8001`.
- Frontend dashboard is open at `/remote-access`.
- Device token was copied from the dashboard.
- Target laptop has dependencies installed.
- Target laptop agent is running with `wss://YOUR-NGROK-URL`.
- Device shows `ONLINE`.
- Dashboard sends a connection request.
- Target laptop user types `YES`.
- Session becomes `ACTIVE`.
- Screen, control, and disk access match the selected permission.

## 14. Security Notes

- Use this only for temporary testing.
- Do not share the ngrok URL or device token publicly.
- Stop the agent when testing is complete.
- Stop ngrok when testing is complete.
- Rotate or delete test device tokens after use.
- Use cloud hosting for stable production access.
- Keep approval logic enabled so the target user must approve each session.
