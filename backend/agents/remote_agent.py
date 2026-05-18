"""
ManageAI Remote Agent.

Install optional dependencies on the target laptop:
    pip install websockets mss pillow pyautogui

Run:
    python remote_agent.py --server ws://127.0.0.1:8001 --token DEVICE_TOKEN

For another device on the same Wi-Fi, do not use 127.0.0.1. Start Django with:
    python manage.py runserver 0.0.0.0:8001

Then use this computer's LAN IP:
    python remote_agent.py --server ws://192.168.1.10:8001 --token DEVICE_TOKEN

The agent never opens browser-local disk access. It connects outbound to ManageAI,
waits for a dashboard session request, asks for local approval in the terminal,
then accepts screen, control, and file commands over the approved WebSocket.
"""

import argparse
import asyncio
import base64
import binascii
import json
import os
import platform
import socket
import struct
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

try:
    import mss
    from PIL import Image, ImageChops
    SCREEN_IMPORT_ERROR = ""
except Exception as exc:
    mss = None
    Image = None
    SCREEN_IMPORT_ERROR = str(exc)

try:
    import pyautogui
    CONTROL_IMPORT_ERROR = ""
except Exception as exc:
    pyautogui = None
    CONTROL_IMPORT_ERROR = str(exc)

try:
    import websockets
except Exception as exc:
    raise SystemExit("Install websockets first: pip install websockets") from exc


class RemoteAgent:
    def __init__(self, server, token, fps=12, quality=76, max_width=1600):
        self.server = self.normalize_server(server)
        self.token = token
        self.fps = max(1, min(fps, 20))
        self.quality = max(35, min(quality, 90))
        self.max_width = max(640, min(max_width, 2560))
        self.active_sessions = set()
        self.streaming = False

    def normalize_server(self, server):
        value = (server or "ws://127.0.0.1:8001").strip().rstrip("/")
        if value.startswith("http://"):
            return f"ws://{value.removeprefix('http://')}"
        if value.startswith("https://"):
            return f"wss://{value.removeprefix('https://')}"
        return value

    @property
    def url(self):
        return f"{self.server}/ws/remote-agent/{self.token}/"

    async def run(self):
        while True:
            try:
                async with websockets.connect(self.url, max_size=8 * 1024 * 1024, open_timeout=30, ping_timeout=30) as ws:
                    await self.hello(ws)
                    heartbeat = asyncio.create_task(self.heartbeat(ws))
                    async for raw in ws:
                        await self.handle(ws, json.loads(raw))
                    heartbeat.cancel()
            except Exception as exc:
                print(f"Disconnected from {self.url}: {exc}. Reconnecting in 3s.")
                self.print_connection_tip(exc)
                if "refused" in str(exc).lower() or "1225" in str(exc):
                    print("Tip: make sure Django is running on that host/port. For another local device, run Django with 0.0.0.0:8001 and use the server computer's LAN IP, not 127.0.0.1.")
                await asyncio.sleep(3)

    def print_connection_tip(self, exc):
        message = str(exc).lower()
        if "timed out" not in message and "handshake" not in message:
            return
        parsed = urlparse(self.server)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        if not host:
            return
        print(f"Checking server reachability at {host}:{port}...")
        try:
            with socket.create_connection((host, port), timeout=5):
                print("TCP port is reachable. If the WebSocket still times out, confirm the backend is running with Daphne/ASGI and the token exists in ManageAI.")
        except OSError as tcp_exc:
            print(f"TCP port is not reachable: {tcp_exc}. Allow inbound TCP {port} in Windows Firewall and make sure both laptops are on the same network.")
            return
        http_scheme = "https" if parsed.scheme == "wss" else "http"
        try:
            with urlopen(f"{http_scheme}://{host}:{port}/", timeout=5) as response:
                print(f"HTTP check returned {response.status}. The server is reachable; retry the agent or restart Django if WebSocket upgrades are stuck.")
        except Exception as http_exc:
            print(f"HTTP check failed: {http_exc}. Check DJANGO_ALLOWED_HOSTS and start Django with: python manage.py runserver 0.0.0.0:{port}")

    async def hello(self, ws):
        await ws.send(json.dumps({"type": "heartbeat", "metadata": self.device_metadata()}))

    async def heartbeat(self, ws):
        while True:
            await asyncio.sleep(10)
            await ws.send(json.dumps({"type": "heartbeat", "metadata": self.device_metadata()}))

    def device_metadata(self):
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "agent_version": "0.1.0",
            "capabilities": {"screen": bool(mss), "control": bool(pyautogui), "files": True, "chunked_transfer": True},
            "dependency_errors": {"screen": SCREEN_IMPORT_ERROR, "control": CONTROL_IMPORT_ERROR},
        }

    async def handle(self, ws, message):
        kind = message.get("type")
        if kind == "session.request":
            await self.ask_approval(ws, message["session"])
        elif kind == "session.disconnect":
            self.active_sessions.discard(message.get("session_token"))
        elif kind == "session.command":
            await self.handle_command(ws, message)
        elif kind == "file.command":
            await self.handle_file(ws, message)
        elif kind == "file.transfer":
            await self.handle_transfer(ws, message)

    async def ask_approval(self, ws, session):
        token = session["token"]
        permission = session["permission"]
        print(f"\nRemote request: {permission} from {session.get('requested_by_name') or 'dashboard'}")
        answer = input("Approve this session? Type YES to approve: ").strip()
        if answer == "YES":
            self.active_sessions.add(token)
            await ws.send(json.dumps({"type": "session.approved", "session_token": token, "answer": {"transport": "websocket-frame-relay"}}))
            asyncio.create_task(self.stream_screen(ws, token, session.get("offer", {}).get("stream") or {}))
        else:
            await ws.send(json.dumps({"type": "session.denied", "session_token": token}))

    async def stream_screen(self, ws, session_token, stream_options=None):
        if not mss or not Image:
            message = "mss and pillow are required for screen capture. Run: pip install mss pillow"
            if SCREEN_IMPORT_ERROR:
                message = f"{message}. Import error: {SCREEN_IMPORT_ERROR}"
            print(message)
            await ws.send(json.dumps({"type": "agent.error", "session_token": session_token, "message": message}))
            return
        stream_options = stream_options or {}
        fps = max(1, min(int(stream_options.get("fps") or self.fps), 20))
        quality = max(35, min(int(stream_options.get("quality") or self.quality), 90))
        max_width = max(640, min(int(stream_options.get("max_width") or self.max_width), 2560))
        try:
            with mss.mss() as screen:
                monitor = screen.monitors[1]
                previous = None
                frame_index = 0
                while session_token in self.active_sessions:
                    started = time.perf_counter()
                    shot = screen.grab(monitor)
                    img = Image.frombytes("RGB", shot.size, shot.rgb)
                    max_height = int(max_width * shot.height / max(shot.width, 1))
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    from io import BytesIO

                    frame_index += 1
                    full = previous is None or frame_index % 30 == 0
                    box = (0, 0, img.width, img.height)
                    if previous is not None and not full:
                        diff = ImageChops.difference(previous, img)
                        changed = diff.getbbox()
                        if not changed:
                            await asyncio.sleep(max(0, (1 / fps) - (time.perf_counter() - started)))
                            continue
                        changed_area = (changed[2] - changed[0]) * (changed[3] - changed[1])
                        full = changed_area > (img.width * img.height * 0.65)
                        box = (0, 0, img.width, img.height) if full else changed
                    chunk = img if full else img.crop(box)
                    buf = BytesIO()
                    chunk.save(buf, format="JPEG", quality=quality, optimize=True)
                    header = {
                        "type": "screen.frame.binary",
                        "session_token": session_token,
                        "format": "jpeg",
                        "full": full,
                        "x": box[0],
                        "y": box[1],
                        "width": box[2] - box[0],
                        "height": box[3] - box[1],
                        "screen_width": img.width,
                        "screen_height": img.height,
                        "ts": time.time(),
                    }
                    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
                    await ws.send(struct.pack("!I", len(header_bytes)) + header_bytes + buf.getvalue())
                    previous = img.copy()
                    await asyncio.sleep(max(0, (1 / fps) - (time.perf_counter() - started)))
        except Exception as exc:
            message = f"Screen capture failed: {exc}"
            print(message)
            await ws.send(json.dumps({"type": "agent.error", "session_token": session_token, "message": message}))

    async def handle_command(self, ws, message):
        if message.get("session_token") not in self.active_sessions or not pyautogui:
            return
        command = message.get("command")
        payload = message.get("payload") or {}
        if command == "mouse":
            action = payload.get("action")
            if "x_ratio" in payload and "y_ratio" in payload:
                width, height = pyautogui.size()
                x = int(float(payload["x_ratio"]) * width)
                y = int(float(payload["y_ratio"]) * height)
            else:
                x, y = int(payload.get("x", 0)), int(payload.get("y", 0))
            if action == "move":
                pyautogui.moveTo(x, y, duration=0)
            elif action == "click":
                pyautogui.click(x, y)
            elif action == "down":
                pyautogui.mouseDown(x, y)
            elif action == "up":
                pyautogui.mouseUp(x, y)
            elif action == "scroll":
                pyautogui.scroll(int(payload.get("delta", 0)))
        elif command == "keyboard":
            text = payload.get("text")
            key = payload.get("key")
            event = payload.get("event", "press")
            if text:
                pyautogui.write(text, interval=0)
            elif key:
                if payload.get("modifiers"):
                    pyautogui.hotkey(*payload["modifiers"], key)
                elif event == "down":
                    pyautogui.keyDown(key)
                elif event == "up":
                    pyautogui.keyUp(key)
                else:
                    pyautogui.press(key)

    async def handle_file(self, ws, message):
        session_token = message.get("session_token")
        action = message.get("action")
        payload = message.get("payload") or {}
        try:
            if action == "drives":
                result = {"path": "Drives", "entries": [{"name": drive["name"], "path": drive["path"], "is_dir": True, "size": 0} for drive in self.drives()]}
            elif action == "list":
                result = self.list_path(payload.get("path") or self.default_root())
            elif action == "upload":
                result = self.upload_chunk(payload)
            elif action == "delete":
                result = self.delete_path(payload["path"])
            else:
                result = {"error": f"Unsupported file action: {action}"}
            await ws.send(json.dumps({"type": "file.result", "session_token": session_token, "action": action, "result": result}))
        except Exception as exc:
            await ws.send(json.dumps({"type": "agent.error", "session_token": session_token, "message": str(exc)}))

    async def handle_transfer(self, ws, message):
        transfer = message.get("transfer") or {}
        path = transfer.get("source_path")
        session_token = message.get("session_token")
        chunk_size = int(transfer.get("chunk_size") or 262144)
        sent = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                sent += len(chunk)
                await ws.send(json.dumps({"type": "transfer.progress", "session_token": session_token, "transfer_id": transfer.get("id"), "bytes": sent, "chunk": base64.b64encode(chunk).decode("ascii")}))
        await ws.send(json.dumps({"type": "transfer.progress", "session_token": session_token, "transfer_id": transfer.get("id"), "complete": True, "bytes": sent}))

    def drives(self):
        if os.name == "nt":
            return [{"name": f"{letter}:", "path": f"{letter}:\\"} for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:\\").exists()]
        return [{"name": "/", "path": "/"}]

    def default_root(self):
        drives = self.drives()
        return drives[0]["path"] if drives else str(Path.home())

    def list_path(self, raw_path):
        root = Path(raw_path)
        entries = []
        for item in root.iterdir():
            try:
                stat = item.stat()
                entries.append({"name": item.name, "path": str(item), "is_dir": item.is_dir(), "size": stat.st_size, "modified": stat.st_mtime})
            except PermissionError:
                entries.append({"name": item.name, "path": str(item), "is_dir": item.is_dir(), "size": 0, "locked": True})
        return {"path": str(root), "entries": sorted(entries, key=lambda row: (not row["is_dir"], row["name"].lower()))}

    def upload_chunk(self, payload):
        directory = Path(payload.get("path") or self.default_root())
        directory.mkdir(parents=True, exist_ok=True)
        filename = Path(payload.get("name") or "upload.bin").name
        target = directory / filename
        mode = "ab" if int(payload.get("offset") or 0) else "wb"
        try:
            chunk = base64.b64decode(payload.get("chunk") or "", validate=True)
        except binascii.Error as exc:
            raise ValueError(f"Invalid upload chunk: {exc}") from exc
        with target.open(mode + "") as handle:
            handle.write(chunk)
        size = target.stat().st_size
        return {"path": str(directory), "uploaded": str(target), "bytes": size, "complete": bool(payload.get("complete"))}

    def delete_path(self, raw_path):
        path = Path(raw_path)
        if path.is_dir():
            raise PermissionError("Folder deletes are intentionally disabled in the starter agent.")
        path.unlink()
        return {"deleted": str(path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="ws://127.0.0.1:8001")
    parser.add_argument("--token", required=True)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--quality", type=int, default=76)
    parser.add_argument("--max-width", type=int, default=1600)
    args = parser.parse_args()
    asyncio.run(RemoteAgent(args.server, args.token, args.fps, args.quality, args.max_width).run())


if __name__ == "__main__":
    main()
