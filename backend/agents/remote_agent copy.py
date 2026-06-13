import argparse
import asyncio
import base64
import binascii
import contextlib
import ctypes
import hashlib
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
import re
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
    import psutil
    PSUTIL_IMPORT_ERROR = ""
except Exception as exc:
    psutil = None
    PSUTIL_IMPORT_ERROR = str(exc)

try:
    import websockets
except Exception as exc:
    raise SystemExit("Install websockets first: pip install websockets") from exc

# ── Windows API constants ─────────────────────────────────────────────────────
DRIVE_UNKNOWN   = 0
DRIVE_NO_ROOT   = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED     = 3
DRIVE_REMOTE    = 4
DRIVE_CDROM     = 5
DRIVE_RAMDISK   = 6

_DTYPE_MAP = {
    DRIVE_UNKNOWN:   "unknown",
    DRIVE_NO_ROOT:   "no_root",
    DRIVE_REMOVABLE: "removable",
    DRIVE_FIXED:     "fixed",
    DRIVE_REMOTE:    "network",
    DRIVE_CDROM:     "cdrom",
    DRIVE_RAMDISK:   "ramdisk",
}


class RemoteAgent:
    def __init__(self, server, token, fps=12, quality=76, max_width=1600):
        self.server = self.normalize_server(server)
        self.token = token
        self.fps = max(1, min(fps, 30))
        self.quality = max(35, min(quality, 92))
        self.max_width = max(640, min(max_width, 2560))
        self.active_sessions = set()
        self.streaming = False
        self.last_drive_signature = None
        self.send_lock = asyncio.Lock()
        self.background_tasks = set()
        # Cache disk media types (SSD/HDD) — refreshed every 60 s
        self._media_type_cache: dict[str, str] = {}
        self._media_type_ts: float = 0.0
        # Cache MTP/portable device enumeration — refreshed every 30 s
        self._portable_cache: list[dict] = []
        self._portable_cache_ts: float = 0.0
        # FIX: Cache tunnel_mode so urlparse isn't called on every property access
        self._tunnel_mode: bool | None = None

    # ── Server helpers ────────────────────────────────────────────────────────

    @property
    def tunnel_mode(self) -> bool:
        # FIX: Cache result instead of re-parsing URL on every access
        if self._tunnel_mode is None:
            host = urlparse(self.server).hostname or ""
            self._tunnel_mode = any(
                m in host.lower()
                for m in ("ngrok", "trycloudflare", "loca.lt", "localhost.run")
            )
        return self._tunnel_mode

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

    # ── Main loop ─────────────────────────────────────────────────────────────

    async def run(self):
        while True:
            # FIX: Reset drive signature on each new connection so a reconnect
            #      after a crash/disconnect re-establishes a clean baseline and
            #      doesn't suppress the first real change event.
            self.last_drive_signature = None

            tasks = []
            try:
                async with websockets.connect(
                    self.url,
                    max_size=32 * 1024 * 1024,
                    open_timeout=30,
                    ping_interval=20,
                    ping_timeout=90,
                    close_timeout=10,
                ) as ws:
                    await self.hello(ws)
                    # FIX: create_background() adds to self.background_tasks AND
                    #      returns the task.  Keep a separate local list for the
                    #      two "owned" tasks so the finally block only cancels
                    #      them once (via background_tasks).  Don't maintain a
                    #      second reference in `tasks` that would cause double-
                    #      cancel.
                    self.create_background(self.heartbeat(ws), "heartbeat")
                    self.create_background(self.monitor_storage(ws), "storage_monitor")
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            continue
                        await self.handle(ws, json.loads(raw))
            except Exception as exc:
                print(f"Disconnected from {self.url}: {exc}. Reconnecting in 3 s.")
                self.print_connection_tip(exc)
                await asyncio.sleep(3)
            finally:
                # FIX: Cancel all background tasks exactly once via the set.
                for task in list(self.background_tasks):
                    task.cancel()
                for task in list(self.background_tasks):
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task
                self.background_tasks.clear()

    def create_background(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self.background_tasks.add(task)

        def cleanup(done):
            self.background_tasks.discard(done)
            with contextlib.suppress(asyncio.CancelledError):
                exc = done.exception()
                if exc:
                    print(f"[bg/{name}] stopped: {exc}")

        task.add_done_callback(cleanup)
        return task

    async def safe_send(self, ws, payload):
        """Send raw bytes or a string safely under the send lock."""
        try:
            async with self.send_lock:
                await ws.send(payload)
            return True
        except Exception as exc:
            print(f"WebSocket send skipped: {exc}")
            return False

    async def send_json(self, ws, payload):
        return await self.safe_send(ws, json.dumps(payload, separators=(",", ":")))

    # ── Connection diagnostics ────────────────────────────────────────────────

    def print_connection_tip(self, exc):
        message = str(exc).lower()
        if "timed out" not in message and "handshake" not in message:
            return
        parsed = urlparse(self.server)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        if not host:
            return
        print(f"Checking server reachability at {host}:{port} …")
        try:
            with socket.create_connection((host, port), timeout=5):
                print("TCP port is reachable. Confirm Django is running with Daphne/ASGI and the token exists in ManageAI.")
        except OSError as tcp_exc:
            print(f"TCP port unreachable: {tcp_exc}. Allow inbound TCP {port} in Windows Firewall.")
            return
        http_scheme = "https" if parsed.scheme == "wss" else "http"
        try:
            with urlopen(f"{http_scheme}://{host}:{port}/", timeout=5) as resp:
                print(f"HTTP check returned {resp.status}. Server is up; retry or restart Django if WebSocket upgrades fail.")
        except Exception as http_exc:
            print(f"HTTP check failed: {http_exc}. Verify DJANGO_ALLOWED_HOSTS and run Django with: python manage.py runserver 0.0.0.0:{port}")

    # ── Heartbeat / hello ─────────────────────────────────────────────────────

    async def hello(self, ws):
        # FIX: device_metadata() calls drives() which can call blocking PowerShell
        #      subprocesses. Offload to thread pool so the event loop isn't stalled.
        metadata = await asyncio.to_thread(self.device_metadata)
        await self.send_json(ws, {"type": "heartbeat", "metadata": metadata})

    async def heartbeat(self, ws):
        while True:
            await asyncio.sleep(10)
            # FIX: Offload blocking device_metadata() / drives() to thread pool.
            metadata = await asyncio.to_thread(self.device_metadata)
            if not await self.send_json(ws, {"type": "heartbeat", "metadata": metadata}):
                return

    def device_metadata(self):
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "agent_version": "2.0.0",
            "capabilities": {
                "screen": bool(mss),
                "control": bool(pyautogui),
                "files": True,
                "chunked_transfer": True,
                "binary_transfer": True,
                "folder_download": True,
                "drive_download": True,
                "usb_monitor": True,
                "android_mtp": True,
                "network_shares": True,
                "telemetry": bool(psutil),
                "drive_media_type": True,
                "clipboard": True,
            },
            "dependency_errors": {
                "screen": SCREEN_IMPORT_ERROR,
                "control": CONTROL_IMPORT_ERROR,
                "telemetry": PSUTIL_IMPORT_ERROR,
            },
            "telemetry": self.telemetry_snapshot(),
            "storage": self.drives(),
        }

    # ── Storage monitor (realtime, 1-second poll) ─────────────────────────────

    async def monitor_storage(self, ws):
        while True:
            await asyncio.sleep(1)
            try:
                # FIX: drives() calls blocking PowerShell subprocesses — offload.
                drives = await asyncio.to_thread(self.drives)
                signature = json.dumps(
                    [
                        {
                            "path": d.get("path"),
                            "name": d.get("name"),
                            "volume_label": d.get("volume_label"),
                            "drive_type": d.get("drive_type"),
                            "category": d.get("category"),
                            "total": d.get("total"),
                        }
                        for d in drives
                    ],
                    sort_keys=True,
                )
                if self.last_drive_signature is None:
                    self.last_drive_signature = signature
                    continue
                if signature != self.last_drive_signature:
                    self.last_drive_signature = signature
                    if not await self.send_json(
                        ws,
                        {
                            "type": "device.storage.changed",
                            "message": "Storage devices changed.",
                            "drives": drives,
                        },
                    ):
                        return
            except Exception as exc:
                if not await self.send_json(ws, {"type": "agent.error", "message": f"Storage monitor failed: {exc}"}):
                    return

    # ── Message dispatcher ────────────────────────────────────────────────────

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

    # ── Session approval ──────────────────────────────────────────────────────

    async def ask_approval(self, ws, session):
        token = session["token"]
        permission = session["permission"]
        print(f"\nRemote request: {permission} from {session.get('requested_by_name') or 'dashboard'}")
        # FIX: input() blocks the event loop — offload to thread pool.
        answer = await asyncio.to_thread(
            lambda: input("Approve this session? Type YES to approve: ").strip()
        )
        if answer == "YES":
            self.active_sessions.add(token)
            await self.send_json(
                ws,
                {
                    "type": "session.approved",
                    "session_token": token,
                    "answer": {"transport": "websocket-frame-relay"},
                },
            )
            self.create_background(
                self.stream_screen(ws, token, session.get("offer", {}).get("stream") or {}),
                "screen_stream",
            )
        else:
            await self.send_json(ws, {"type": "session.denied", "session_token": token})

    # ── Screen streaming ──────────────────────────────────────────────────────

    async def stream_screen(self, ws, session_token, stream_options=None):
        if not mss or not Image:
            msg = "mss and pillow are required for screen capture. Run: pip install mss pillow"
            if SCREEN_IMPORT_ERROR:
                msg = f"{msg}. Import error: {SCREEN_IMPORT_ERROR}"
            print(msg)
            await self.send_json(ws, {"type": "agent.error", "session_token": session_token, "message": msg})
            return
        stream_options = stream_options or {}
        fps = max(1, min(int(stream_options.get("fps") or self.fps), 30))
        quality = max(35, min(int(stream_options.get("quality") or self.quality), 92))
        max_width = max(640, min(int(stream_options.get("max_width") or self.max_width), 2560))
        if self.tunnel_mode:
            fps = min(fps, 12)
            quality = min(quality, 70)
            max_width = min(max_width, 1280)
        try:
            from io import BytesIO
            # FIX: mss.mss() is the correct context manager; there is no mss.MSS class.
            #      The original getattr(mss, "MSS", None) always returned None, falling
            #      back to mss.mss() anyway — but the conditional was misleading and
            #      would break if mss ever gained an MSS attribute with different semantics.
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
                    if not await self.safe_send(
                        ws, struct.pack("!I", len(header_bytes)) + header_bytes + buf.getvalue()
                    ):
                        return
                    previous = img.copy()
                    await asyncio.sleep(max(0, (1 / fps) - (time.perf_counter() - started)))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            msg = f"Screen capture failed: {exc}"
            print(msg)
            await self.send_json(ws, {"type": "agent.error", "session_token": session_token, "message": msg})

    # ── Input control ─────────────────────────────────────────────────────────

    async def handle_command(self, ws, message):
        session_token = message.get("session_token")
        if session_token not in self.active_sessions:
            return
        command = message.get("command")
        payload = message.get("payload") or {}
        if command == "clipboard.set":
            await asyncio.to_thread(self.set_clipboard_text, payload.get("text") or "")
            return
        if command == "clipboard.get":
            text = await asyncio.to_thread(self.get_clipboard_text)
            await self.send_json(ws, {"type": "clipboard.data", "session_token": session_token, "text": text})
            return
        if not pyautogui:
            return
        if command == "mouse":
            action = payload.get("action")
            button = payload.get("button") or "left"
            if "x_ratio" in payload and "y_ratio" in payload:
                width, height = pyautogui.size()
                x = int(float(payload["x_ratio"]) * width)
                y = int(float(payload["y_ratio"]) * height)
            else:
                x, y = int(payload.get("x", 0)), int(payload.get("y", 0))
            if action == "move":
                pyautogui.moveTo(x, y, duration=0)
            elif action == "click":
                pyautogui.click(x, y, button=button)
            elif action == "down":
                pyautogui.mouseDown(x, y, button=button)
            elif action == "up":
                pyautogui.mouseUp(x, y, button=button)
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

    def set_clipboard_text(self, text: str) -> None:
        if os.name != "nt":
            return
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "$input | Set-Clipboard"],
            input=text,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def get_clipboard_text(self) -> str:
        if os.name != "nt":
            return ""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Get-Clipboard -Raw"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout if result.returncode == 0 else ""

    # ── File commands ─────────────────────────────────────────────────────────

    async def handle_file(self, ws, message):
        session_token = message.get("session_token")
        action = message.get("action")
        payload = message.get("payload") or {}
        try:
            # FIX: All file operations are blocking I/O (disk, subprocess).
            #      Wrap every branch in asyncio.to_thread so the event loop is
            #      never stalled while waiting for filesystem or PowerShell calls.
            if action == "drives":
                result = await asyncio.to_thread(
                    lambda: {"path": "Drives", "entries": self.drives()}
                )
            elif action == "list":
                result = await asyncio.to_thread(
                    self.list_path, payload.get("path") or self.default_root()
                )
            elif action == "upload":
                result = await asyncio.to_thread(self.upload_chunk, payload)
            elif action == "delete":
                result = await asyncio.to_thread(self.delete_path, payload["path"])
            else:
                result = {"error": f"Unsupported file action: {action}"}
            await self.send_json(
                ws,
                {"type": "file.result", "session_token": session_token, "action": action, "result": result},
            )
        except Exception as exc:
            await self.send_json(ws, {"type": "agent.error", "session_token": session_token, "message": str(exc)})

    # ── File transfer (binary WebSocket frames) ───────────────────────────────

    async def handle_transfer(self, ws, message):
        transfer = message.get("transfer") or {}
        path = transfer.get("source_path")
        session_token = message.get("session_token")
        use_binary = transfer.get("binary", True)

        default_chunk = 512 * 1024 if self.tunnel_mode else 2 * 1024 * 1024
        chunk_size = max(64 * 1024, min(int(transfer.get("chunk_size") or default_chunk), 4 * 1024 * 1024))

        prepared_path = None
        cleanup_zip = None   # FIX: renamed from cleanup_path for clarity
        cleanup_dir = None

        try:
            source = Path(path) if not str(path or "").startswith("shell:") else None
            send_name = (
                transfer.get("original_name")
                or (source.name if source else str(path).removeprefix("shell:").split("/")[-1])
                or "download"
            )

            # MTP / shell: path — copy to temp first
            if str(path or "").startswith("shell:"):
                if not await self.send_json(
                    ws,
                    {
                        "type": "transfer.progress",
                        "session_token": session_token,
                        "transfer_id": transfer.get("id"),
                        "packaging": True,
                        "bytes": 0,
                        "name": send_name,
                    },
                ):
                    return
                prepared_path, cleanup_dir = await asyncio.to_thread(self.prepare_shell_download, path)
                if prepared_path.is_dir():
                    prepared_path = await asyncio.to_thread(self.zip_folder, prepared_path)
                    # FIX: The zipped file lives inside cleanup_dir; track it
                    #      separately so we don't unlink inside a directory we're
                    #      about to rmtree (which would be redundant but harmless),
                    #      and so we always remove the temp zip even if cleanup_dir
                    #      is the parent.
                    cleanup_zip = prepared_path
                    send_name = f"{send_name.rstrip('.zip')}.zip"

            # Regular directory — zip on demand
            if source is not None and source.is_dir():
                if not await self.send_json(
                    ws,
                    {
                        "type": "transfer.progress",
                        "session_token": session_token,
                        "transfer_id": transfer.get("id"),
                        "packaging": True,
                        "bytes": 0,
                        "name": f"{send_name}.zip",
                    },
                ):
                    return
                prepared_path = await asyncio.to_thread(self.zip_folder, source)
                cleanup_zip = prepared_path
                send_name = f"{send_name.rstrip('.zip')}.zip"
            elif source is not None:
                prepared_path = source

            total = prepared_path.stat().st_size
            sent = 0
            transfer_start = time.perf_counter()
            digest = hashlib.sha256()

            with prepared_path.open("rb") as handle:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        break
                    sent += len(chunk)
                    digest.update(chunk)

                    elapsed = max(time.perf_counter() - transfer_start, 0.001)
                    speed = sent / elapsed
                    eta = int((total - sent) / speed) if speed > 0 else 0

                    if use_binary:
                        header = {
                            "type": "transfer.chunk.binary",
                            "session_token": session_token,
                            "transfer_id": transfer.get("id"),
                            "bytes": sent,
                            "total": total,
                            "name": send_name,
                            "speed": round(speed),
                            "eta": eta,
                        }
                        header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
                        frame = struct.pack("!I", len(header_bytes)) + header_bytes + chunk
                        if not await self.safe_send(ws, frame):
                            return
                    else:
                        if not await self.send_json(
                            ws,
                            {
                                "type": "transfer.progress",
                                "session_token": session_token,
                                "transfer_id": transfer.get("id"),
                                "bytes": sent,
                                "total": total,
                                "name": send_name,
                                "speed": round(speed),
                                "eta": eta,
                                "chunk": base64.b64encode(chunk).decode("ascii"),
                            },
                        ):
                            return

                    await asyncio.sleep(0)

            await self.send_json(
                ws,
                {
                    "type": "transfer.progress",
                    "session_token": session_token,
                    "transfer_id": transfer.get("id"),
                    "complete": True,
                    "bytes": sent,
                    "total": total,
                    "name": send_name,
                    "sha256": digest.hexdigest(),
                    "speed": round(sent / max(time.perf_counter() - transfer_start, 0.001)),
                    "eta": 0,
                },
            )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.send_json(
                ws,
                {"type": "agent.error", "session_token": session_token, "message": f"Transfer failed: {exc}"},
            )
        finally:
            # FIX: Unlink the zip file first, then remove the temp directory.
            #      Previously both cleanup_path (the zip) and cleanup_dir could
            #      refer to the same path hierarchy, causing a double-delete
            #      attempt.  Now cleanup_zip is always the zip archive (or None)
            #      and cleanup_dir is always a directory (or None); removing the
            #      file before the directory avoids any ordering issue.
            if cleanup_zip:
                with contextlib.suppress(OSError):
                    cleanup_zip.unlink(missing_ok=True)
            if cleanup_dir:
                shutil.rmtree(cleanup_dir, ignore_errors=True)

    # ── Folder zipper ─────────────────────────────────────────────────────────

    def zip_folder(self, folder_path):
        folder_path = Path(folder_path)
        archive = tempfile.NamedTemporaryFile(prefix="manageai-folder-", suffix=".zip", delete=False)
        archive.close()
        with zipfile.ZipFile(archive.name, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
            for root, dirs, files in os.walk(folder_path, onerror=lambda exc: None):
                root_path = Path(root)
                for dirname in dirs:
                    full_dir = root_path / dirname
                    arcname = full_dir.relative_to(folder_path).as_posix() + "/"
                    zipf.writestr(arcname, "")
                for filename in files:
                    full_path = root_path / filename
                    try:
                        arcname = full_path.relative_to(folder_path)
                        zipf.write(full_path, arcname.as_posix())
                    except (OSError, PermissionError):
                        continue
        return Path(archive.name)

    # ── Shell/MTP download helper ─────────────────────────────────────────────

    def prepare_shell_download(self, raw_path):
        """Copy a single MTP/shell item to a temp directory for streaming."""
        segments = [s for s in str(raw_path or "").removeprefix("shell:").split("/") if s]
        if not segments:
            raise PermissionError("Portable device path is empty.")
        parent_segments = segments[:-1]
        item_name = segments[-1]
        temp_dir = Path(tempfile.mkdtemp(prefix="manageai-mtp-"))
        parent_json = json.dumps(parent_segments).replace("'", "''")
        item_json   = json.dumps(item_name).replace("'", "''")
        temp_json   = json.dumps(str(temp_dir)).replace("'", "''")
        script = (
            f"$segments = ConvertFrom-Json '{parent_json}'; "
            f"$itemName = ConvertFrom-Json '{item_json}'; "
            f"$targetPath = ConvertFrom-Json '{temp_json}'; "
            "function Find-ShellChild($folder, $name) { "
            "if($name -match '^@(\\d+)$'){ "
            "$targetIndex=[int]$Matches[1]; $currentIndex=0; "
            "foreach($child in $folder.Items()){ if($currentIndex -eq $targetIndex){ return $child }; $currentIndex++ } "
            "} "
            "foreach($child in $folder.Items()){ "
            "$childName=($child.Name -as [string]).Trim(); $wanted=($name -as [string]).Trim(); "
            "if([string]::Equals($childName,$wanted,[System.StringComparison]::OrdinalIgnoreCase)){ return $child } "
            "} "
            "$portable=@(); $hasDrive=$false; "
            "foreach($child in $folder.Items()){ "
            "$childPath=$child.Path; "
            "if($childPath -and $childPath -match '^[A-Z]:\\\\$'){ $hasDrive=$true } else { $portable += $child } "
            "} "
            "if($hasDrive -and $portable.Count -eq 1){ return $portable[0] } "
            "return $null "
            "} "
            "$shell=New-Object -ComObject Shell.Application; "
            "$folder=$shell.Namespace(17); "
            "foreach($segment in $segments){ "
            "$next=Find-ShellChild $folder $segment; "
            "if($null -eq $next){ throw ('Portable folder not found: '+$segment) } "
            "$folder=$next.GetFolder; "
            "} "
            "$item=Find-ShellChild $folder $itemName; "
            "if($null -eq $item){ throw ('Portable item not found: '+$itemName) } "
            "$target=$shell.Namespace($targetPath); "
            "$before=@(Get-ChildItem -LiteralPath $targetPath -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }); "
            "$target.CopyHere($item, 16); "
            "$deadline=(Get-Date).AddMinutes(30); $lastSize=-1; $stable=0; $after=@(); "
            "do { "
            "  Start-Sleep -Milliseconds 500; "
            "  $after=@(Get-ChildItem -LiteralPath $targetPath -Force | Where-Object { $before -notcontains $_.FullName }); "
            "  if($after.Count -gt 0){ "
            "    $candidate=$after[0]; "
            "    if($candidate.PSIsContainer){ $size=1 } else { $size=[int64]$candidate.Length } "
            "    if($size -eq $lastSize){ $stable++ } else { $stable=0; $lastSize=$size } "
            "  } "
            "} while(($after.Count -eq 0 -or $stable -lt 3) -and (Get-Date) -lt $deadline); "
            "if($after.Count -eq 0){ throw 'Portable device copy produced no file.' } "
            "$after[0].FullName"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=60 * 31,
        )
        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise PermissionError(result.stderr.strip() or "Windows denied portable device copy.")
        copied = Path(result.stdout.strip().splitlines()[-1])
        if not copied.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise FileNotFoundError("Portable device copy finished without a local file.")
        return copied, temp_dir

    # ══════════════════════════════════════════════════════════════════════════
    # DRIVE ENUMERATION
    # ══════════════════════════════════════════════════════════════════════════

    def drives(self):
        seen_paths: set[str] = set()
        result = []

        if os.name == "nt":
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for index, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                if not bitmask & (1 << index):
                    continue
                path = f"{letter}:\\"
                dtype_id = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path))
                dtype = _DTYPE_MAP.get(dtype_id, "unknown")
                if dtype in ("no_root", "unknown"):
                    continue
                info = self.drive_info(path, dtype)
                norm = path.upper()
                if norm not in seen_paths:
                    seen_paths.add(norm)
                    result.append(info)

            for dev in self.portable_devices():
                norm = str(dev.get("path", "")).upper()
                if norm not in seen_paths:
                    seen_paths.add(norm)
                    result.append(dev)

            for share in self.network_shares_unmapped():
                norm = str(share.get("path", "")).upper()
                if norm not in seen_paths:
                    seen_paths.add(norm)
                    result.append(share)

        else:
            result.append(self.drive_info("/", "root"))
            if psutil:
                for part in psutil.disk_partitions(all=True):
                    if part.mountpoint == "/":
                        continue
                    norm = part.mountpoint.upper()
                    if norm in seen_paths:
                        continue
                    seen_paths.add(norm)
                    result.append(self.drive_info(part.mountpoint, part.fstype or "mount"))

        return result

    # ── SSD / HDD media-type detection (cached 60 s) ─────────────────────────

    def _get_disk_media_types(self) -> dict[str, str]:
        if os.name != "nt":
            return {}
        now = time.monotonic()
        if self._media_type_cache and (now - self._media_type_ts) < 60:
            return self._media_type_cache

        script = (
            "$result = @{}; "
            "foreach ($disk in (Get-PhysicalDisk)) { "
            "  $diskNum = $disk.DeviceId; "
            "  $mediaType = $disk.MediaType; "
            "  foreach ($partition in (Get-Partition -DiskNumber $diskNum -ea SilentlyContinue)) { "
            "    $letter = $partition.DriveLetter; "
            "    if ($letter) { $result[$letter.ToString()] = $mediaType } "
            "  } "
            "} "
            "$result | ConvertTo-Json -Compress"
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, timeout=8,
            )
            if out.returncode == 0 and out.stdout.strip():
                raw = json.loads(out.stdout.strip())
                if isinstance(raw, dict):
                    self._media_type_cache = {k.upper(): str(v) for k, v in raw.items()}
                    self._media_type_ts = now
                    return self._media_type_cache
        except Exception:
            pass
        return {}

    def _media_type_for_letter(self, letter: str) -> str:
        mt = self._get_disk_media_types().get(letter.upper().rstrip(":\\"), "")
        if "SSD" in mt or mt == "4":
            return "SSD"
        if "HDD" in mt or mt == "3":
            return "HDD"
        if mt and mt not in ("0", "Unspecified", ""):
            return mt
        return ""

    # ── Drive info builder ────────────────────────────────────────────────────

    def drive_info(self, path: str, drive_type: str = "fixed") -> dict:
        raw_label = self.volume_label(path)

        if raw_label:
            label = raw_label
        elif drive_type == "fixed":
            label = "Local Disk"
        elif drive_type == "removable":
            label = "Removable Disk"
        elif drive_type == "network":
            label = "Network Drive"
        elif drive_type == "cdrom":
            label = "CD/DVD Drive"
        elif drive_type == "ramdisk":
            label = "RAM Disk"
        else:
            label = "Local Disk"

        stripped = path.rstrip("\\/")
        letter_suffix = f" ({stripped})" if len(stripped) == 2 and stripped[1] == ":" else ""
        display_name = f"{label}{letter_suffix}"

        drive_letter = stripped[0] if len(stripped) >= 1 else ""
        if drive_type == "network":
            category = "Network Share"
        elif drive_type == "cdrom":
            category = "CD/DVD Drive"
        elif drive_type == "ramdisk":
            category = "RAM Disk"
        elif drive_type == "removable":
            if "SD" in raw_label.upper() or "SDCARD" in raw_label.upper().replace(" ", ""):
                category = "SD Card"
            else:
                category = "USB Storage"
        elif drive_type == "fixed":
            mt = self._media_type_for_letter(drive_letter)
            if mt == "SSD":
                category = "SSD"
            elif mt == "HDD":
                category = "HDD"
            else:
                category = "Internal Drive"
        else:
            category = "Unknown"

        payload: dict = {
            "name": display_name,
            "path": path,
            "is_dir": True,
            "size": 0,
            "drive": True,
            "drive_type": drive_type,
            "category": category,
            "free": 0,
            "total": 0,
            "used": 0,
            "usage_percent": 0,
            "health": "unknown",
            "removable": drive_type in {"removable", "cdrom"},
            "volume_label": raw_label,
            "display_name": display_name,
            "connection_type": self._connection_type(drive_type, drive_letter),
        }

        try:
            usage = shutil.disk_usage(path)
            payload.update({
                "size": usage.total,
                "free": usage.free,
                "total": usage.total,
                "used": usage.used,
                "usage_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0,
                "health": (
                    "critical" if usage.total and usage.free / usage.total < 0.08
                    else "warning" if usage.total and usage.free / usage.total < 0.18
                    else "healthy"
                ),
            })
        except OSError:
            payload["health"] = "locked"

        if psutil:
            try:
                counters = psutil.disk_io_counters(perdisk=True) or {}
                for key in (drive_letter, f"{drive_letter}:", stripped):
                    disk_counter = counters.get(key)
                    if disk_counter:
                        payload["read_bytes"]  = getattr(disk_counter, "read_bytes", 0)
                        payload["write_bytes"] = getattr(disk_counter, "write_bytes", 0)
                        break
            except Exception:
                pass

        return payload

    def _connection_type(self, drive_type: str, letter: str) -> str:
        if drive_type == "network":
            return "Network"
        if drive_type == "removable":
            return "USB"
        if drive_type == "cdrom":
            return "Optical"
        if drive_type == "ramdisk":
            return "RAM"
        mt = self._media_type_for_letter(letter)
        if mt == "SSD":
            return "SSD (SATA/NVMe)"
        if mt == "HDD":
            return "HDD (SATA)"
        return "Internal"

    # ── Windows volume label ──────────────────────────────────────────────────

    def volume_label(self, path: str) -> str:
        if os.name != "nt":
            return ""
        try:
            name_buf = ctypes.create_unicode_buffer(261)
            fs_buf   = ctypes.create_unicode_buffer(261)
            serial   = ctypes.c_ulong()
            max_comp = ctypes.c_ulong()
            flags    = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(path),
                name_buf, len(name_buf),
                ctypes.byref(serial),
                ctypes.byref(max_comp),
                ctypes.byref(flags),
                fs_buf, len(fs_buf),
            )
            return name_buf.value.strip() if ok else ""
        except Exception:
            return ""

    # ── Portable / MTP / Android devices ─────────────────────────────────────

    def portable_devices(self) -> list[dict]:
        if os.name != "nt":
            return []

        now = time.monotonic()
        if self._portable_cache and (now - self._portable_cache_ts) < 30:
            return self._portable_cache

        devices: list[dict] = []

        try:
            script = (
                "$shell=New-Object -ComObject Shell.Application; "

                "function Parse-Bytes($text){ "
                "$s=($text -as [string]).Trim(); if(-not $s){ return [int64]0 }; "
                "$m=[regex]::Match($s,'([0-9]+(?:[\\.,][0-9]+)?)\\s*(B|KB|MB|GB|TB)','IgnoreCase'); "
                "if(-not $m.Success){ return [int64]0 }; "
                "$n=[double]($m.Groups[1].Value -replace ',','.'); $u=$m.Groups[2].Value.ToUpper(); "
                "switch($u){ "
                " 'KB'{return [int64]($n*1KB)} 'MB'{return [int64]($n*1MB)} "
                " 'GB'{return [int64]($n*1GB)} 'TB'{return [int64]($n*1TB)} "
                " default{return [int64]$n} } "
                "} "

                "function Scan-SizeColumns($folder,$child){ "
                "$found=@(); "
                "for($i=0;$i -lt 500;$i++){ "
                "  $raw=$folder.GetDetailsOf($child,$i); "
                "  if(-not $raw){ continue }; "
                "  $b=Parse-Bytes $raw; "
                "  if($b -gt 1MB){ "
                "    $hdr=$folder.GetDetailsOf($null,$i); "
                "    $found+=[pscustomobject]@{h=($hdr -as [string]);v=$b;raw=$raw} "
                "  } "
                "} "
                "return $found "
                "} "

                "function Storage-Metrics($item){ "
                "$total=[int64]0; $free=[int64]0; "
                "try{ "
                "  $devFolder=$item.GetFolder; "
                "  foreach($child in $devFolder.Items()){ "
                "    $cols=Scan-SizeColumns $devFolder $child; "
                "    if($cols.Count -ge 1){ "
                "      $sorted=$cols|Sort-Object v -Descending; "
                "      $total=$sorted[0].v; "
                "      $freeEntry=$cols|Where-Object{$_.h -match 'free|avail|libre|frei|vrij|disponible|格|여유|boş'}|Sort-Object v -Descending|Select-Object -First 1; "
                "      if($freeEntry){ $free=$freeEntry.v } "
                "      elseif($cols.Count -ge 2){ $free=$sorted[1].v } "
                "      break "
                "    } "
                "  } "
                "}catch{} "
                "@{total=$total;free=$free} "
                "} "

                "$items=@(); $index=0; "
                "$root=$shell.Namespace(17); "
                "foreach($item in $root.Items()){ "
                "  $p=$item.Path; "
                "  if($p -and $p -match '^[A-Z]:\\\\$'){ $index++; continue } "
                "  $type=[string]$item.Type; "
                "  $m=Storage-Metrics $item; "
                "  $tot=[int64]$m.total; $fr=[int64]$m.free; "
                "  $used=[Math]::Max(0,$tot-$fr); "
                "  $pct=if($tot -gt 0){[Math]::Round(($used/$tot)*100,1)}else{0}; "
                "  $items+=[pscustomobject]@{"
                "    name=$item.Name; path=('shell:@'+$index); "
                "    is_dir=$true; drive=$true; drive_type='portable'; "
                "    device_type=$type; health='healthy'; removable=$true; "
                "    total=$tot; free=$fr; used=$used; usage_percent=$pct "
                "  }; "
                "  $index++ "
                "} "
                "$items|ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    if not item.get("name"):
                        continue
                    name = item["name"]
                    device_type_hint = str(item.get("device_type", "")).lower()
                    is_camera = "camera" in name.lower() or "ptp" in device_type_hint
                    is_android = (
                        "android" in name.lower()
                        or "phone" in device_type_hint
                        or "portable media player" in device_type_hint
                        or (not is_camera and "portable" in device_type_hint)
                    )
                    if is_android:
                        category = "Android Device"
                    elif is_camera:
                        category = "Camera (PTP)"
                    else:
                        category = "Portable Device"
                    item["category"] = category
                    item["display_name"] = name
                    item["connection_type"] = "USB (MTP/PTP)"
                    devices.append(item)
        except Exception as exc:
            print(f"[portable_devices] Shell.Application failed: {exc}")

        if not devices:
            devices.extend(self._portable_devices_wmi())

        self._portable_cache = devices
        self._portable_cache_ts = time.monotonic()

        return devices

    def _portable_devices_wmi(self) -> list[dict]:
        try:
            script = (
                "Get-PnpDevice | "
                "Where-Object { $_.Class -eq 'WPD' -or $_.FriendlyName -match 'MTP|Android|iPhone|portable' } | "
                "Select-Object FriendlyName, Status | "
                "ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            out = []
            for i, item in enumerate(data):
                name = item.get("FriendlyName") or f"Portable Device {i}"
                status = item.get("Status", "OK")
                out.append({
                    "name": name,
                    "path": f"shell:@wmi_{i}",
                    "display_name": name,
                    "is_dir": True,
                    "drive": True,
                    "drive_type": "portable",
                    "category": "Android Device" if "android" in name.lower() else "Portable Device",
                    "health": "healthy" if status == "OK" else "warning",
                    "total": 0, "free": 0, "used": 0, "usage_percent": 0,
                    "removable": True,
                    "connection_type": "USB (MTP/WPD)",
                    "wmi_only": True,
                })
            return out
        except Exception:
            return []

    # ── Network shares (unmapped / UNC) ───────────────────────────────────────

    def network_shares_unmapped(self) -> list[dict]:
        if os.name != "nt":
            return []
        shares: list[dict] = []
        try:
            result = subprocess.run(
                ["net", "use"],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.splitlines()
            for line in lines:
                parts = line.split()
                for part in parts:
                    if part.startswith("\\\\") and len(part) > 4:
                        unc = part
                        name = unc.lstrip("\\").replace("\\", " › ")
                        shares.append({
                            "name": f"Network Share ({name})",
                            "display_name": f"Network Share ({name})",
                            "path": unc,
                            "is_dir": True,
                            "drive": True,
                            "drive_type": "network",
                            "category": "Network Share",
                            "health": "healthy",
                            "total": 0, "free": 0, "used": 0, "usage_percent": 0,
                            "removable": False,
                            "connection_type": "Network (SMB)",
                            "volume_label": "",
                        })
        except Exception:
            pass

        for share in shares:
            try:
                usage = shutil.disk_usage(share["path"])
                share.update({
                    "total": usage.total,
                    "free": usage.free,
                    "used": usage.used,
                    "usage_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0,
                    "size": usage.total,
                })
            except OSError:
                share["health"] = "locked"

        return shares

    # ══════════════════════════════════════════════════════════════════════════
    # FILE SYSTEM HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def telemetry_snapshot(self) -> dict:
        if not psutil:
            return {}
        try:
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        try:
            net = psutil.net_io_counters()
        except Exception:
            net = None
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage(str(Path.home().anchor or "/")).percent,
            "battery": battery.percent if battery else None,
            "network_sent": getattr(net, "bytes_sent", 0) if net else 0,
            "network_recv": getattr(net, "bytes_recv", 0) if net else 0,
            "processes": len(psutil.pids()),
        }

    def default_root(self) -> str:
        drives = self.drives()
        return drives[0]["path"] if drives else str(Path.home())

    def list_path(self, raw_path: str) -> dict:
        if str(raw_path or "").startswith("shell:"):
            return self.list_shell_path(raw_path)
        root = Path(raw_path)
        entries = []
        try:
            items = list(root.iterdir())
        except PermissionError:
            return {"path": str(root), "entries": [], "error": "Permission denied"}
        for item in items:
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except PermissionError:
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": 0,
                    "locked": True,
                })
            except OSError:
                pass
        return {
            "path": str(root),
            "entries": sorted(entries, key=lambda r: (not r["is_dir"], r["name"].lower())),
        }

    def list_shell_path(self, raw_path: str) -> dict:
        """List contents of a shell:/MTP path via PowerShell Shell.Application."""
        segments = [s for s in str(raw_path or "").removeprefix("shell:").split("/") if s]
        segments_json = json.dumps(segments).replace("'", "''")
        script = (
            f"$segments = ConvertFrom-Json '{segments_json}'; "
            "function Find-ShellChild($folder, $name) { "
            "if($name -match '^@(\\d+)$'){ "
            "$targetIndex=[int]$Matches[1]; $currentIndex=0; "
            "foreach($child in $folder.Items()){ if($currentIndex -eq $targetIndex){ return $child }; $currentIndex++ } "
            "} "
            "foreach($child in $folder.Items()){ "
            "$childName=($child.Name -as [string]).Trim(); $wanted=($name -as [string]).Trim(); "
            "if([string]::Equals($childName,$wanted,[System.StringComparison]::OrdinalIgnoreCase)){ return $child } "
            "} "
            "$portable=@(); $hasDrive=$false; "
            "foreach($child in $folder.Items()){ "
            "$childPath=$child.Path; "
            "if($childPath -and $childPath -match '^[A-Z]:\\\\$'){ $hasDrive=$true } else { $portable += $child } "
            "} "
            "if($hasDrive -and $portable.Count -eq 1){ return $portable[0] } "
            "return $null "
            "} "
            "$shell=New-Object -ComObject Shell.Application; "
            "$folder=$shell.Namespace(17); "
            "foreach($segment in $segments){ "
            "$item=Find-ShellChild $folder $segment; "
            "if($null -eq $item){ throw ('Portable folder not found: '+$segment) } "
            "$folder=$item.GetFolder; "
            "} "
            "$items=@(); "
            "$childIndex=0; "
            "foreach($item in $folder.Items()){ "
            "$childSegments=@($segments)+@('@'+$childIndex); "
            # FIX: Scan columns for the first NON-EMPTY size value rather than
            #      breaking on the first column whose header matches the pattern.
            #      The original loop broke immediately on a matching header even
            #      when GetDetailsOf() returned an empty string for that item,
            #      leaving sizeText blank for most files.
            "$sizeText=''; "
            "for($i=0;$i -lt 160;$i++){ "
            "  $h=$folder.GetDetailsOf($null,$i); "
            "  if($h -and $h -match 'Size|Capacity'){ "
            "    $v=$folder.GetDetailsOf($item,$i); "
            "    if($v){ $sizeText=$v; break } "
            "  } "
            "} "
            "$modifiedText=''; "
            "for($i=0;$i -lt 160;$i++){ "
            "  $h=$folder.GetDetailsOf($null,$i); "
            "  if($h -and $h -match 'Date modified|Modified|Date'){ "
            "    $v=$folder.GetDetailsOf($item,$i); "
            "    if($v){ $modifiedText=$v; break } "
            "  } "
            "} "
            "$items += [pscustomobject]@{"
            "  name=$item.Name; "
            "  path=('shell:' + ($childSegments -join '/')); "
            "  is_dir=$item.IsFolder; "
            "  size=0; size_text=$sizeText; modified_text=$modifiedText; modified=$null; portable=$true; type=$item.Type"
            "}; "
            "$childIndex++ "
            "} "
            "$items | ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=12,
        )
        if result.returncode != 0:
            raise PermissionError(result.stderr.strip() or "Windows denied portable device access.")
        data = json.loads(result.stdout or "[]")
        if isinstance(data, dict):
            data = [data]
        for item in data:
            if item.get("size_text"):
                item["size"] = self.parse_size_text(item.get("size_text"))
        return {
            "path": raw_path,
            "entries": sorted(data, key=lambda r: (not r.get("is_dir"), str(r.get("name", "")).lower())),
        }

    def parse_size_text(self, value) -> int:
        match = re.search(r"([0-9]+(?:[\.,][0-9]+)?)\s*(B|KB|MB|GB|TB)", str(value or ""), re.I)
        if not match:
            return 0
        number = float(match.group(1).replace(",", "."))
        unit = match.group(2).upper()
        powers = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}
        return int(number * (1024 ** powers.get(unit, 0)))

    def upload_chunk(self, payload: dict) -> dict:
        directory = Path(payload.get("path") or self.default_root())
        directory.mkdir(parents=True, exist_ok=True)
        filename = Path(payload.get("name") or "upload.bin").name
        target = directory / filename
        mode = "ab" if int(payload.get("offset") or 0) else "wb"
        try:
            chunk = base64.b64decode(payload.get("chunk") or "", validate=True)
        except binascii.Error as exc:
            raise ValueError(f"Invalid upload chunk: {exc}") from exc
        with target.open(mode) as handle:
            handle.write(chunk)
        size = target.stat().st_size
        return {
            "path": str(directory),
            "uploaded": str(target),
            "bytes": size,
            "complete": bool(payload.get("complete")),
        }

    def delete_path(self, raw_path: str) -> dict:
        path = Path(raw_path)
        if path.is_dir():
            raise PermissionError("Folder deletes are intentionally disabled in the agent.")
        path.unlink()
        return {"deleted": str(path)}


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ManageAI Remote Agent v2.0")
    parser.add_argument("--server",    default="ws://127.0.0.1:8001", help="WebSocket server URL")
    parser.add_argument("--token",     required=True,                  help="Device token from ManageAI dashboard")
    parser.add_argument("--fps",       type=int, default=12,           help="Screen capture FPS (1-30)")
    parser.add_argument("--quality",   type=int, default=76,           help="JPEG quality (35-92)")
    parser.add_argument("--max-width", type=int, default=1600,         help="Max screen width in pixels")
    args = parser.parse_args()
    asyncio.run(RemoteAgent(args.server, args.token, args.fps, args.quality, args.max_width).run())


if __name__ == "__main__":
    main()
