"""
ManageAI Remote Agent v3.0
Advanced Edition — Multi-Monitor · Terminal Shell · Process Manager
"""

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
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

try:
    import mss
    from PIL import Image, ImageChops, ImageDraw, ImageFont
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

# ── Terminal constants ────────────────────────────────────────────────────────
TERMINAL_HISTORY_LIMIT = 2000   # lines kept per session
TERMINAL_OUTPUT_CHUNK  = 4096   # bytes per read

# ── Process monitor constants ─────────────────────────────────────────────────
PROCESS_POLL_INTERVAL = 2.0     # seconds between process snapshots
PROCESS_TOP_N         = 60      # max processes sent per update


class RemoteAgent:
    def __init__(self, server, token, fps=12, quality=76, max_width=1600):
        self.server    = self.normalize_server(server)
        self.token     = token
        self.fps       = max(1,   min(fps,       30))
        self.quality   = max(35,  min(quality,   92))
        self.max_width = max(640, min(max_width, 2560))

        self.active_sessions:     set        = set()
        self.streaming:           bool       = False
        self.last_drive_signature: str|None  = None
        self.send_lock            = asyncio.Lock()
        self.background_tasks:    set        = set()

        # ── Caches ────────────────────────────────────────────────────────────
        self._media_type_cache:    dict[str, str] = {}
        self._media_type_ts:       float          = 0.0
        self._portable_cache:      list[dict]     = []
        self._portable_cache_ts:   float          = 0.0
        self._tunnel_mode:         bool|None      = None

        # ── Multi-monitor state ───────────────────────────────────────────────
        # Maps session_token → monitor_index (0 = combined/all, 1+ = specific)
        self._session_monitor:     dict[str, int] = {}

        # ── Terminal sessions ─────────────────────────────────────────────────
        # Maps terminal_id → TerminalSession
        self._terminals:           dict[str, "TerminalSession"] = {}

        # ── Process watch ─────────────────────────────────────────────────────
        self._last_process_snapshot: list[dict] = []

    # ══════════════════════════════════════════════════════════════════════════
    # SERVER / URL HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    @property
    def tunnel_mode(self) -> bool:
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

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN CONNECTION LOOP
    # ══════════════════════════════════════════════════════════════════════════

    async def run(self):
        while True:
            self.last_drive_signature = None
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
                    self.create_background(self.heartbeat(ws),       "heartbeat")
                    self.create_background(self.monitor_storage(ws), "storage_monitor")
                    self.create_background(self.monitor_processes(ws), "process_monitor")
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            continue
                        await self.handle(ws, json.loads(raw))
            except Exception as exc:
                print(f"Disconnected from {self.url}: {exc}. Reconnecting in 3 s.")
                self.print_connection_tip(exc)
                await asyncio.sleep(3)
            finally:
                # Close all terminal processes cleanly
                for term in list(self._terminals.values()):
                    term.kill()
                self._terminals.clear()

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
        try:
            async with self.send_lock:
                await ws.send(payload)
            return True
        except Exception as exc:
            print(f"WebSocket send skipped: {exc}")
            return False

    async def send_json(self, ws, payload):
        return await self.safe_send(ws, json.dumps(payload, separators=(",", ":")))

    # ══════════════════════════════════════════════════════════════════════════
    # CONNECTION DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════════════════

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
                print("TCP port is reachable.")
        except OSError as tcp_exc:
            print(f"TCP port unreachable: {tcp_exc}.")

    # ══════════════════════════════════════════════════════════════════════════
    # HEARTBEAT / HELLO
    # ══════════════════════════════════════════════════════════════════════════

    async def hello(self, ws):
        metadata = await asyncio.to_thread(self.device_metadata)
        await self.send_json(ws, {"type": "heartbeat", "metadata": metadata})

    async def heartbeat(self, ws):
        while True:
            await asyncio.sleep(10)
            metadata = await asyncio.to_thread(self.device_metadata)
            if not await self.send_json(ws, {"type": "heartbeat", "metadata": metadata}):
                return

    def device_metadata(self):
        monitors = self.list_monitors()
        return {
            "hostname":   socket.gethostname(),
            "platform":   platform.platform(),
            "agent_version": "3.0.0",
            "capabilities": {
                "screen":           bool(mss),
                "control":          bool(pyautogui),
                "files":            True,
                "chunked_transfer": True,
                "binary_transfer":  True,
                "folder_download":  True,
                "drive_download":   True,
                "usb_monitor":      True,
                "android_mtp":      True,
                "network_shares":   True,
                "telemetry":        bool(psutil),
                "drive_media_type": True,
                "clipboard":        True,
                # v3 capabilities
                "multi_monitor":    bool(mss) and len(monitors) > 1,
                "terminal":         True,
                "process_manager":  bool(psutil),
                "file_search":      True,
                "screenshot_annotation": bool(Image),
            },
            "dependency_errors": {
                "screen":    SCREEN_IMPORT_ERROR,
                "control":   CONTROL_IMPORT_ERROR,
                "telemetry": PSUTIL_IMPORT_ERROR,
            },
            "telemetry": self.telemetry_snapshot(),
            "storage":   self.drives(),
            "monitors":  monitors,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # MULTI-MONITOR  (NEW v3)
    # ══════════════════════════════════════════════════════════════════════════

    def list_monitors(self) -> list[dict]:
        """Return info for every connected display."""
        if not mss:
            return []
        try:
            with mss.mss() as sct:
                result = []
                for i, m in enumerate(sct.monitors):
                    if i == 0:
                        label = "All Monitors (Combined)"
                    else:
                        label = f"Monitor {i} ({m['width']}×{m['height']})"
                    result.append({
                        "index":  i,
                        "label":  label,
                        "left":   m["left"],
                        "top":    m["top"],
                        "width":  m["width"],
                        "height": m["height"],
                        "primary": i == 1,
                    })
                return result
        except Exception:
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # STORAGE MONITOR
    # ══════════════════════════════════════════════════════════════════════════

    async def monitor_storage(self, ws):
        while True:
            await asyncio.sleep(1)
            try:
                drives = await asyncio.to_thread(self.drives)
                signature = json.dumps(
                    [{"path": d.get("path"), "name": d.get("name"),
                      "volume_label": d.get("volume_label"),
                      "drive_type": d.get("drive_type"),
                      "category": d.get("category"),
                      "total": d.get("total")} for d in drives],
                    sort_keys=True,
                )
                if self.last_drive_signature is None:
                    self.last_drive_signature = signature
                    continue
                if signature != self.last_drive_signature:
                    self.last_drive_signature = signature
                    if not await self.send_json(ws, {
                        "type": "device.storage.changed",
                        "message": "Storage devices changed.",
                        "drives": drives,
                    }):
                        return
            except Exception as exc:
                if not await self.send_json(ws, {"type": "agent.error",
                                                  "message": f"Storage monitor failed: {exc}"}):
                    return

    # ══════════════════════════════════════════════════════════════════════════
    # PROCESS MONITOR  (NEW v3)
    # ══════════════════════════════════════════════════════════════════════════

    async def monitor_processes(self, ws):
        """Broadcast process list every PROCESS_POLL_INTERVAL seconds."""
        if not psutil:
            return
        while True:
            await asyncio.sleep(PROCESS_POLL_INTERVAL)
            try:
                snapshot = await asyncio.to_thread(self._collect_processes)
                if not await self.send_json(ws, {
                    "type":      "process.snapshot",
                    "processes": snapshot,
                    "ts":        time.time(),
                }):
                    return
            except Exception as exc:
                # Non-fatal — just skip this tick
                print(f"[process_monitor] {exc}")

    def _collect_processes(self) -> list[dict]:
        if not psutil:
            return []
        procs = []
        for proc in psutil.process_iter(
            ["pid", "name", "status", "cpu_percent", "memory_info",
             "create_time", "username", "cmdline", "num_threads"]
        ):
            try:
                info = proc.info
                mem  = info.get("memory_info")
                procs.append({
                    "pid":        info["pid"],
                    "name":       info["name"] or "",
                    "status":     info["status"] or "",
                    "cpu":        round(info["cpu_percent"] or 0, 1),
                    "mem":        mem.rss if mem else 0,
                    "threads":    info.get("num_threads") or 0,
                    "user":       info.get("username") or "",
                    "started":    info.get("create_time") or 0,
                    "cmd":        " ".join(info.get("cmdline") or [])[:200],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU desc, then memory desc
        procs.sort(key=lambda p: (-p["cpu"], -p["mem"]))
        return procs[:PROCESS_TOP_N]

    def _kill_process(self, pid: int, signal_name: str = "TERMINATE") -> dict:
        """Kill or signal a process by PID."""
        if not psutil:
            raise RuntimeError("psutil not available")
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            if signal_name == "KILL":
                proc.kill()
            elif signal_name == "SUSPEND":
                proc.suspend()
            elif signal_name == "RESUME":
                proc.resume()
            else:
                proc.terminate()
            return {"ok": True, "pid": pid, "name": name, "action": signal_name}
        except psutil.NoSuchProcess:
            raise RuntimeError(f"Process {pid} not found")
        except psutil.AccessDenied:
            raise RuntimeError(f"Access denied killing PID {pid}")

    # ══════════════════════════════════════════════════════════════════════════
    # MESSAGE DISPATCHER
    # ══════════════════════════════════════════════════════════════════════════

    async def handle(self, ws, message):
        kind = message.get("type")
        if kind == "session.request":
            await self.ask_approval(ws, message["session"])
        elif kind == "session.disconnect":
            token = message.get("session_token")
            self.active_sessions.discard(token)
            self._session_monitor.pop(token, None)
        elif kind == "session.command":
            await self.handle_command(ws, message)
        elif kind == "file.command":
            await self.handle_file(ws, message)
        elif kind == "file.transfer":
            await self.handle_transfer(ws, message)
        # ── v3 new message types ──────────────────────────────────────────────
        elif kind == "monitor.select":
            await self.handle_monitor_select(ws, message)
        elif kind == "terminal.command":
            await self.handle_terminal(ws, message)
        elif kind == "process.command":
            await self.handle_process_command(ws, message)

    # ══════════════════════════════════════════════════════════════════════════
    # SESSION APPROVAL
    # ══════════════════════════════════════════════════════════════════════════

    async def ask_approval(self, ws, session):
        token      = session["token"]
        permission = session["permission"]
        print(f"\nRemote request: {permission} from {session.get('requested_by_name') or 'dashboard'}")
        answer = await asyncio.to_thread(
            lambda: input("Approve this session? Type YES to approve: ").strip()
        )
        if answer == "YES":
            self.active_sessions.add(token)
            # Default to primary monitor (index 1)
            self._session_monitor[token] = 1
            await self.send_json(ws, {
                "type":         "session.approved",
                "session_token": token,
                "answer":       {"transport": "websocket-frame-relay"},
                "monitors":     self.list_monitors(),
            })
            self.create_background(
                self.stream_screen(ws, token, session.get("offer", {}).get("stream") or {}),
                "screen_stream",
            )
        else:
            await self.send_json(ws, {"type": "session.denied", "session_token": token})

    # ══════════════════════════════════════════════════════════════════════════
    # MULTI-MONITOR SELECTION  (NEW v3)
    # ══════════════════════════════════════════════════════════════════════════

    async def handle_monitor_select(self, ws, message):
        """Switch the active stream to a different monitor."""
        session_token = message.get("session_token")
        if session_token not in self.active_sessions:
            return
        index = int(message.get("monitor_index", 1))
        monitors = self.list_monitors()
        if index < 0 or index >= len(monitors):
            await self.send_json(ws, {
                "type":    "agent.error",
                "message": f"Monitor index {index} out of range (0–{len(monitors)-1})",
            })
            return
        self._session_monitor[session_token] = index
        await self.send_json(ws, {
            "type":          "monitor.selected",
            "session_token": session_token,
            "monitor":       monitors[index],
        })

    # ══════════════════════════════════════════════════════════════════════════
    # SCREEN STREAMING  (enhanced for multi-monitor)
    # ══════════════════════════════════════════════════════════════════════════

    async def stream_screen(self, ws, session_token, stream_options=None):
        if not mss or not Image:
            msg = "mss and pillow required. Run: pip install mss pillow"
            await self.send_json(ws, {"type": "agent.error",
                                      "session_token": session_token, "message": msg})
            return
        stream_options = stream_options or {}
        fps       = max(1,   min(int(stream_options.get("fps")       or self.fps),       30))
        quality   = max(35,  min(int(stream_options.get("quality")   or self.quality),   92))
        max_width = max(640, min(int(stream_options.get("max_width") or self.max_width), 2560))
        if self.tunnel_mode:
            fps       = min(fps, 12)
            quality   = min(quality, 70)
            max_width = min(max_width, 1280)

        try:
            from io import BytesIO
            with mss.mss() as screen:
                previous    = None
                frame_index = 0

                while session_token in self.active_sessions:
                    started = time.perf_counter()

                    # Dynamic monitor selection per session
                    monitor_index = self._session_monitor.get(session_token, 1)
                    monitors = screen.monitors
                    if monitor_index >= len(monitors):
                        monitor_index = 1
                    monitor = monitors[monitor_index]

                    shot = screen.grab(monitor)
                    img  = Image.frombytes("RGB", shot.size, shot.rgb)

                    # Annotate monitor label in corner (lightweight, 1 frame only on switch)
                    max_height = int(max_width * shot.height / max(shot.width, 1))
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                    frame_index += 1
                    full = previous is None or frame_index % 30 == 0
                    box  = (0, 0, img.width, img.height)

                    if previous is not None and not full:
                        diff    = ImageChops.difference(previous, img)
                        changed = diff.getbbox()
                        if not changed:
                            await asyncio.sleep(max(0, (1 / fps) - (time.perf_counter() - started)))
                            continue
                        changed_area = (changed[2] - changed[0]) * (changed[3] - changed[1])
                        full = changed_area > (img.width * img.height * 0.65)
                        box  = (0, 0, img.width, img.height) if full else changed

                    chunk = img if full else img.crop(box)
                    buf   = BytesIO()
                    chunk.save(buf, format="JPEG", quality=quality, optimize=True)

                    header = {
                        "type":          "screen.frame.binary",
                        "session_token": session_token,
                        "format":        "jpeg",
                        "full":          full,
                        "x":             box[0],
                        "y":             box[1],
                        "width":         box[2] - box[0],
                        "height":        box[3] - box[1],
                        "screen_width":  img.width,
                        "screen_height": img.height,
                        "monitor_index": monitor_index,
                        "ts":            time.time(),
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
            await self.send_json(ws, {"type": "agent.error",
                                      "session_token": session_token, "message": msg})

    # ══════════════════════════════════════════════════════════════════════════
    # INPUT CONTROL
    # ══════════════════════════════════════════════════════════════════════════

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
            await self.send_json(ws, {"type": "clipboard.data",
                                       "session_token": session_token, "text": text})
            return
        # Screenshot with annotation
        if command == "screenshot.annotate":
            await self._handle_screenshot_annotate(ws, session_token, payload)
            return

        if not pyautogui:
            return

        if command == "mouse":
            action = payload.get("action")
            button = payload.get("button") or "left"
            if "x_ratio" in payload and "y_ratio" in payload:
                # Account for active monitor offset
                monitor_index = self._session_monitor.get(session_token, 1)
                mon_info = self._get_monitor_rect(monitor_index)
                w = mon_info["width"]
                h = mon_info["height"]
                x = mon_info["left"] + int(float(payload["x_ratio"]) * w)
                y = mon_info["top"]  + int(float(payload["y_ratio"]) * h)
            else:
                x, y = int(payload.get("x", 0)), int(payload.get("y", 0))

            if   action == "move":   pyautogui.moveTo(x, y, duration=0)
            elif action == "click":  pyautogui.click(x, y, button=button)
            elif action == "down":   pyautogui.mouseDown(x, y, button=button)
            elif action == "up":     pyautogui.mouseUp(x, y, button=button)
            elif action == "double": pyautogui.doubleClick(x, y, button=button)
            elif action == "scroll": pyautogui.scroll(int(payload.get("delta", 0)), x=x, y=y)

        elif command == "keyboard":
            text  = payload.get("text")
            key   = payload.get("key")
            event = payload.get("event", "press")
            if text:
                pyautogui.write(text, interval=0)
            elif key:
                if payload.get("modifiers"):
                    pyautogui.hotkey(*payload["modifiers"], key)
                elif event == "down": pyautogui.keyDown(key)
                elif event == "up":   pyautogui.keyUp(key)
                else:                 pyautogui.press(key)

    def _get_monitor_rect(self, index: int) -> dict:
        """Return left/top/width/height for a monitor index, or primary if unavailable."""
        if not mss:
            return {"left": 0, "top": 0, "width": 1920, "height": 1080}
        try:
            with mss.mss() as sct:
                monitors = sct.monitors
                idx = index if 0 <= index < len(monitors) else 1
                m   = monitors[idx]
                return {"left": m["left"], "top": m["top"],
                        "width": m["width"], "height": m["height"]}
        except Exception:
            return {"left": 0, "top": 0, "width": 1920, "height": 1080}

    async def _handle_screenshot_annotate(self, ws, session_token, payload):
        """Take a screenshot, draw annotations, and send back as base64 JPEG."""
        if not mss or not Image:
            return
        try:
            monitor_index = self._session_monitor.get(session_token, 1)
            from io import BytesIO
            with mss.mss() as sct:
                monitors = sct.monitors
                idx = monitor_index if 0 <= monitor_index < len(monitors) else 1
                shot = sct.grab(monitors[idx])
                img  = Image.frombytes("RGB", shot.size, shot.rgb)

            draw        = ImageDraw.Draw(img)
            annotations = payload.get("annotations") or []
            for ann in annotations:
                kind  = ann.get("type")
                color = ann.get("color", "red")
                if kind == "rect":
                    draw.rectangle(
                        [ann["x1"], ann["y1"], ann["x2"], ann["y2"]],
                        outline=color, width=ann.get("width", 3)
                    )
                elif kind == "circle":
                    cx, cy, r = ann["cx"], ann["cy"], ann.get("r", 20)
                    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color,
                                 width=ann.get("width", 3))
                elif kind == "text":
                    try:
                        font = ImageFont.load_default()
                    except Exception:
                        font = None
                    draw.text((ann["x"], ann["y"]), ann.get("text", ""),
                              fill=color, font=font)
                elif kind == "arrow":
                    draw.line([ann["x1"], ann["y1"], ann["x2"], ann["y2"]],
                              fill=color, width=ann.get("width", 3))

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=88)
            encoded = base64.b64encode(buf.getvalue()).decode()
            await self.send_json(ws, {
                "type":          "screenshot.annotated",
                "session_token": session_token,
                "image":         encoded,
                "monitor_index": monitor_index,
            })
        except Exception as exc:
            await self.send_json(ws, {"type": "agent.error",
                                       "message": f"Screenshot annotation failed: {exc}"})

    def set_clipboard_text(self, text: str) -> None:
        if os.name != "nt":
            try:
                subprocess.run(["xclip", "-selection", "clipboard"],
                               input=text.encode(), timeout=5)
            except Exception:
                pass
            return
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", "$input | Set-Clipboard"],
            input=text, capture_output=True, text=True, timeout=5,
        )

    def get_clipboard_text(self) -> str:
        if os.name != "nt":
            try:
                result = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                                        capture_output=True, timeout=5)
                return result.stdout.decode(errors="replace")
            except Exception:
                return ""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", "Get-Clipboard -Raw"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout if result.returncode == 0 else ""

    # ══════════════════════════════════════════════════════════════════════════
    # TERMINAL SHELL  (NEW v3)
    # ══════════════════════════════════════════════════════════════════════════

    async def handle_terminal(self, ws, message):
        """Dispatch terminal sub-commands."""
        session_token = message.get("session_token")
        if session_token not in self.active_sessions:
            return
        action      = message.get("action")
        terminal_id = message.get("terminal_id") or ""
        payload     = message.get("payload") or {}

        try:
            if action == "create":
                await self._terminal_create(ws, session_token, terminal_id, payload)
            elif action == "input":
                await self._terminal_input(terminal_id, payload.get("data", ""))
            elif action == "resize":
                await self._terminal_resize(terminal_id,
                                            payload.get("cols", 80),
                                            payload.get("rows", 24))
            elif action == "close":
                await self._terminal_close(ws, session_token, terminal_id)
            elif action == "list":
                terms = [{"id": tid, "title": t.title, "alive": t.alive}
                         for tid, t in self._terminals.items()]
                await self.send_json(ws, {
                    "type":          "terminal.list",
                    "session_token": session_token,
                    "terminals":     terms,
                })
            else:
                await self.send_json(ws, {"type": "agent.error",
                                           "message": f"Unknown terminal action: {action}"})
        except Exception as exc:
            await self.send_json(ws, {
                "type":          "agent.error",
                "session_token": session_token,
                "message":       f"Terminal error: {exc}",
            })

    async def _terminal_create(self, ws, session_token, terminal_id, payload):
        """Spawn a new shell process and start piping its output."""
        if terminal_id in self._terminals:
            await self.send_json(ws, {"type": "agent.error",
                                       "message": f"Terminal {terminal_id} already exists"})
            return

        shell   = payload.get("shell") or self._default_shell()
        cwd     = payload.get("cwd")   or str(Path.home())
        cols    = int(payload.get("cols", 80))
        rows    = int(payload.get("rows", 24))
        title   = payload.get("title") or f"Terminal {len(self._terminals)+1}"

        term = TerminalSession(terminal_id, shell, cwd, cols, rows, title)
        await asyncio.to_thread(term.start)
        self._terminals[terminal_id] = term

        await self.send_json(ws, {
            "type":          "terminal.created",
            "session_token": session_token,
            "terminal_id":   terminal_id,
            "shell":         shell,
            "cwd":           cwd,
            "cols":          cols,
            "rows":          rows,
            "title":         title,
        })

        # Background task: relay output → websocket
        self.create_background(
            self._terminal_output_relay(ws, session_token, terminal_id),
            f"term_relay_{terminal_id}",
        )

    async def _terminal_output_relay(self, ws, session_token, terminal_id):
        """Read terminal process stdout/stderr and forward to client."""
        term = self._terminals.get(terminal_id)
        if not term:
            return
        loop = asyncio.get_running_loop()
        try:
            while term.alive:
                try:
                    data = await asyncio.wait_for(
                        loop.run_in_executor(None, term.read_output),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue
                if data is None:
                    break
                if not await self.send_json(ws, {
                    "type":          "terminal.output",
                    "session_token": session_token,
                    "terminal_id":   terminal_id,
                    "data":          data,
                }):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.send_json(ws, {
                "type":    "agent.error",
                "message": f"Terminal relay error: {exc}",
            })
        finally:
            exit_code = term.exit_code
            self._terminals.pop(terminal_id, None)
            await self.send_json(ws, {
                "type":          "terminal.closed",
                "session_token": session_token,
                "terminal_id":   terminal_id,
                "exit_code":     exit_code,
            })

    async def _terminal_input(self, terminal_id, data: str):
        term = self._terminals.get(terminal_id)
        if term and term.alive:
            await asyncio.to_thread(term.write_input, data)

    async def _terminal_resize(self, terminal_id, cols: int, rows: int):
        term = self._terminals.get(terminal_id)
        if term and term.alive:
            await asyncio.to_thread(term.resize, cols, rows)

    async def _terminal_close(self, ws, session_token, terminal_id):
        term = self._terminals.pop(terminal_id, None)
        if term:
            await asyncio.to_thread(term.kill)
        await self.send_json(ws, {
            "type":          "terminal.closed",
            "session_token": session_token,
            "terminal_id":   terminal_id,
            "exit_code":     None,
        })

    def _default_shell(self) -> str:
        if os.name == "nt":
            # Prefer PowerShell if available
            ps = shutil.which("pwsh") or shutil.which("powershell")
            return ps or "cmd.exe"
        return os.environ.get("SHELL", "/bin/bash")

    # ══════════════════════════════════════════════════════════════════════════
    # PROCESS MANAGER COMMANDS  (NEW v3)
    # ══════════════════════════════════════════════════════════════════════════

    async def handle_process_command(self, ws, message):
        session_token = message.get("session_token")
        if session_token not in self.active_sessions:
            return
        action  = message.get("action")
        payload = message.get("payload") or {}

        try:
            if action == "list":
                snapshot = await asyncio.to_thread(self._collect_processes)
                await self.send_json(ws, {
                    "type":          "process.list",
                    "session_token": session_token,
                    "processes":     snapshot,
                    "ts":            time.time(),
                })

            elif action == "kill":
                pid    = int(payload.get("pid", 0))
                sig    = str(payload.get("signal", "TERMINATE")).upper()
                result = await asyncio.to_thread(self._kill_process, pid, sig)
                await self.send_json(ws, {
                    "type":          "process.killed",
                    "session_token": session_token,
                    "result":        result,
                })

            elif action == "details":
                pid     = int(payload.get("pid", 0))
                details = await asyncio.to_thread(self._process_details, pid)
                await self.send_json(ws, {
                    "type":          "process.details",
                    "session_token": session_token,
                    "details":       details,
                })

            elif action == "start":
                cmd  = payload.get("cmd", "")
                cwd  = payload.get("cwd") or str(Path.home())
                result = await asyncio.to_thread(self._start_process, cmd, cwd)
                await self.send_json(ws, {
                    "type":          "process.started",
                    "session_token": session_token,
                    "result":        result,
                })

            elif action == "search":
                query = payload.get("query", "").lower()
                all_procs = await asyncio.to_thread(self._collect_processes)
                matched = [p for p in all_procs
                           if query in p["name"].lower() or query in p["cmd"].lower()]
                await self.send_json(ws, {
                    "type":          "process.search.result",
                    "session_token": session_token,
                    "processes":     matched,
                    "query":         query,
                })

            else:
                await self.send_json(ws, {"type": "agent.error",
                                           "message": f"Unknown process action: {action}"})
        except Exception as exc:
            await self.send_json(ws, {
                "type":          "agent.error",
                "session_token": session_token,
                "message":       str(exc),
            })

    def _process_details(self, pid: int) -> dict:
        if not psutil:
            raise RuntimeError("psutil not available")
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                mem = p.memory_info()
                return {
                    "pid":         p.pid,
                    "name":        p.name(),
                    "exe":         p.exe() if hasattr(p, "exe") else "",
                    "status":      p.status(),
                    "cpu":         p.cpu_percent(interval=0.1),
                    "mem_rss":     mem.rss,
                    "mem_vms":     mem.vms,
                    "threads":     p.num_threads(),
                    "connections": len(p.connections(kind="all")),
                    "open_files":  len(p.open_files()),
                    "user":        p.username(),
                    "started":     p.create_time(),
                    "parent_pid":  p.ppid(),
                    "cmdline":     " ".join(p.cmdline()),
                    "environ_count": len(p.environ()),
                    "nice":        p.nice(),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            raise RuntimeError(str(exc))

    def _start_process(self, cmd: str, cwd: str) -> dict:
        if not cmd.strip():
            raise ValueError("Empty command")
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"pid": proc.pid, "cmd": cmd}

    # ══════════════════════════════════════════════════════════════════════════
    # FILE COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    async def handle_file(self, ws, message):
        session_token = message.get("session_token")
        action  = message.get("action")
        payload = message.get("payload") or {}
        try:
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
            # ── v3 new file actions ───────────────────────────────────────────
            elif action == "search":
                result = await asyncio.to_thread(
                    self.search_files,
                    payload.get("root")    or self.default_root(),
                    payload.get("query")   or "",
                    int(payload.get("max_results", 200)),
                )
            elif action == "stat":
                result = await asyncio.to_thread(self.stat_path, payload["path"])
            elif action == "rename":
                result = await asyncio.to_thread(
                    self.rename_path, payload["path"], payload["new_name"]
                )
            elif action == "mkdir":
                result = await asyncio.to_thread(self.make_dir, payload["path"])
            else:
                result = {"error": f"Unsupported file action: {action}"}
            await self.send_json(ws, {
                "type":          "file.result",
                "session_token": session_token,
                "action":        action,
                "result":        result,
            })
        except Exception as exc:
            await self.send_json(ws, {"type": "agent.error",
                                       "session_token": session_token, "message": str(exc)})

    # ── v3 File helpers ───────────────────────────────────────────────────────

    def search_files(self, root: str, query: str, max_results: int = 200) -> dict:
        """Recursive filename search under root."""
        root_path = Path(root)
        pattern   = query.lower()
        results   = []
        try:
            for item in root_path.rglob("*"):
                if pattern in item.name.lower():
                    try:
                        st = item.stat()
                        results.append({
                            "name":     item.name,
                            "path":     str(item),
                            "is_dir":   item.is_dir(),
                            "size":     st.st_size,
                            "modified": st.st_mtime,
                        })
                    except OSError:
                        pass
                    if len(results) >= max_results:
                        break
        except PermissionError:
            pass
        return {"query": query, "root": root, "results": results, "count": len(results)}

    def stat_path(self, raw_path: str) -> dict:
        p  = Path(raw_path)
        st = p.stat()
        return {
            "path":     str(p),
            "name":     p.name,
            "is_dir":   p.is_dir(),
            "size":     st.st_size,
            "modified": st.st_mtime,
            "created":  st.st_ctime,
            "accessed": st.st_atime,
            "mode":     oct(st.st_mode),
        }

    def rename_path(self, raw_path: str, new_name: str) -> dict:
        p    = Path(raw_path)
        dest = p.parent / Path(new_name).name
        p.rename(dest)
        return {"renamed": str(dest)}

    def make_dir(self, raw_path: str) -> dict:
        p = Path(raw_path)
        p.mkdir(parents=True, exist_ok=True)
        return {"created": str(p)}

    # ══════════════════════════════════════════════════════════════════════════
    # FILE TRANSFER
    # ══════════════════════════════════════════════════════════════════════════

    async def handle_transfer(self, ws, message):
        transfer       = message.get("transfer") or {}
        path           = transfer.get("source_path")
        session_token  = message.get("session_token")
        use_binary     = transfer.get("binary", True)

        default_chunk  = 512 * 1024 if self.tunnel_mode else 2 * 1024 * 1024
        chunk_size     = max(64 * 1024,
                             min(int(transfer.get("chunk_size") or default_chunk),
                                 4 * 1024 * 1024))

        prepared_path  = None
        cleanup_zip    = None
        cleanup_dir    = None

        try:
            source    = Path(path) if not str(path or "").startswith("shell:") else None
            send_name = (
                transfer.get("original_name")
                or (source.name if source else str(path).removeprefix("shell:").split("/")[-1])
                or "download"
            )

            if str(path or "").startswith("shell:"):
                if not await self.send_json(ws, {
                    "type": "transfer.progress", "session_token": session_token,
                    "transfer_id": transfer.get("id"), "packaging": True,
                    "bytes": 0, "name": send_name,
                }):
                    return
                prepared_path, cleanup_dir = await asyncio.to_thread(
                    self.prepare_shell_download, path
                )
                if prepared_path.is_dir():
                    prepared_path = await asyncio.to_thread(self.zip_folder, prepared_path)
                    cleanup_zip   = prepared_path
                    send_name     = f"{send_name.rstrip('.zip')}.zip"

            if source is not None and source.is_dir():
                if not await self.send_json(ws, {
                    "type": "transfer.progress", "session_token": session_token,
                    "transfer_id": transfer.get("id"), "packaging": True,
                    "bytes": 0, "name": f"{send_name}.zip",
                }):
                    return
                prepared_path = await asyncio.to_thread(self.zip_folder, source)
                cleanup_zip   = prepared_path
                send_name     = f"{send_name.rstrip('.zip')}.zip"
            elif source is not None:
                prepared_path = source

            total          = prepared_path.stat().st_size
            sent           = 0
            transfer_start = time.perf_counter()
            digest         = hashlib.sha256()

            with prepared_path.open("rb") as handle:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        break
                    sent += len(chunk)
                    digest.update(chunk)

                    elapsed = max(time.perf_counter() - transfer_start, 0.001)
                    speed   = sent / elapsed
                    eta     = int((total - sent) / speed) if speed > 0 else 0

                    if use_binary:
                        header = {
                            "type": "transfer.chunk.binary",
                            "session_token": session_token,
                            "transfer_id": transfer.get("id"),
                            "bytes": sent, "total": total,
                            "name": send_name,
                            "speed": round(speed), "eta": eta,
                        }
                        hb    = json.dumps(header, separators=(",", ":")).encode("utf-8")
                        frame = struct.pack("!I", len(hb)) + hb + chunk
                        if not await self.safe_send(ws, frame):
                            return
                    else:
                        if not await self.send_json(ws, {
                            "type": "transfer.progress",
                            "session_token": session_token,
                            "transfer_id": transfer.get("id"),
                            "bytes": sent, "total": total,
                            "name": send_name, "speed": round(speed), "eta": eta,
                            "chunk": base64.b64encode(chunk).decode("ascii"),
                        }):
                            return
                    await asyncio.sleep(0)

            await self.send_json(ws, {
                "type": "transfer.progress",
                "session_token": session_token,
                "transfer_id": transfer.get("id"),
                "complete": True, "bytes": sent, "total": total,
                "name": send_name,
                "sha256": digest.hexdigest(),
                "speed": round(sent / max(time.perf_counter() - transfer_start, 0.001)),
                "eta": 0,
            })

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.send_json(ws, {"type": "agent.error",
                                       "session_token": session_token,
                                       "message": f"Transfer failed: {exc}"})
        finally:
            if cleanup_zip:
                with contextlib.suppress(OSError):
                    cleanup_zip.unlink(missing_ok=True)
            if cleanup_dir:
                shutil.rmtree(cleanup_dir, ignore_errors=True)

    # ══════════════════════════════════════════════════════════════════════════
    # FOLDER ZIPPER
    # ══════════════════════════════════════════════════════════════════════════

    def zip_folder(self, folder_path):
        folder_path = Path(folder_path)
        archive     = tempfile.NamedTemporaryFile(
            prefix="manageai-folder-", suffix=".zip", delete=False
        )
        archive.close()
        with zipfile.ZipFile(archive.name, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
            for root, dirs, files in os.walk(folder_path, onerror=lambda e: None):
                root_path = Path(root)
                for dirname in dirs:
                    full_dir = root_path / dirname
                    arcname  = full_dir.relative_to(folder_path).as_posix() + "/"
                    zipf.writestr(arcname, "")
                for filename in files:
                    full_path = root_path / filename
                    try:
                        arcname = full_path.relative_to(folder_path)
                        zipf.write(full_path, arcname.as_posix())
                    except (OSError, PermissionError):
                        continue
        return Path(archive.name)

    # ══════════════════════════════════════════════════════════════════════════
    # SHELL / MTP DOWNLOAD
    # ══════════════════════════════════════════════════════════════════════════

    def prepare_shell_download(self, raw_path):
        segments     = [s for s in str(raw_path or "").removeprefix("shell:").split("/") if s]
        if not segments:
            raise PermissionError("Portable device path is empty.")
        parent_segs  = segments[:-1]
        item_name    = segments[-1]
        temp_dir     = Path(tempfile.mkdtemp(prefix="manageai-mtp-"))
        parent_json  = json.dumps(parent_segs).replace("'", "''")
        item_json    = json.dumps(item_name).replace("'", "''")
        temp_json    = json.dumps(str(temp_dir)).replace("'", "''")
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
                path     = f"{letter}:\\"
                dtype_id = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path))
                dtype    = _DTYPE_MAP.get(dtype_id, "unknown")
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

    def _get_disk_media_types(self) -> dict[str, str]:
        if os.name != "nt":
            return {}
        now = time.monotonic()
        if self._media_type_cache and (now - self._media_type_ts) < 60:
            return self._media_type_cache
        script = (
            "$result = @{}; "
            "foreach ($disk in (Get-PhysicalDisk)) { "
            "  $diskNum = $disk.DeviceId; $mediaType = $disk.MediaType; "
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
                    self._media_type_ts    = now
                    return self._media_type_cache
        except Exception:
            pass
        return {}

    def _media_type_for_letter(self, letter: str) -> str:
        mt = self._get_disk_media_types().get(letter.upper().rstrip(":\\"), "")
        if "SSD" in mt or mt == "4": return "SSD"
        if "HDD" in mt or mt == "3": return "HDD"
        if mt and mt not in ("0", "Unspecified", ""): return mt
        return ""

    def drive_info(self, path: str, drive_type: str = "fixed") -> dict:
        raw_label = self.volume_label(path)
        if raw_label: label = raw_label
        elif drive_type == "fixed":     label = "Local Disk"
        elif drive_type == "removable": label = "Removable Disk"
        elif drive_type == "network":   label = "Network Drive"
        elif drive_type == "cdrom":     label = "CD/DVD Drive"
        elif drive_type == "ramdisk":   label = "RAM Disk"
        else:                           label = "Local Disk"

        stripped      = path.rstrip("\\/")
        letter_suffix = f" ({stripped})" if len(stripped) == 2 and stripped[1] == ":" else ""
        display_name  = f"{label}{letter_suffix}"
        drive_letter  = stripped[0] if len(stripped) >= 1 else ""

        if drive_type == "network":   category = "Network Share"
        elif drive_type == "cdrom":   category = "CD/DVD Drive"
        elif drive_type == "ramdisk": category = "RAM Disk"
        elif drive_type == "removable":
            category = "SD Card" if ("SD" in raw_label.upper() or "SDCARD" in raw_label.upper().replace(" ", "")) else "USB Storage"
        elif drive_type == "fixed":
            mt = self._media_type_for_letter(drive_letter)
            category = {"SSD": "SSD", "HDD": "HDD"}.get(mt, "Internal Drive")
        else:
            category = "Unknown"

        payload: dict = {
            "name": display_name, "path": path, "is_dir": True, "size": 0,
            "drive": True, "drive_type": drive_type, "category": category,
            "free": 0, "total": 0, "used": 0, "usage_percent": 0,
            "health": "unknown", "removable": drive_type in {"removable", "cdrom"},
            "volume_label": raw_label, "display_name": display_name,
            "connection_type": self._connection_type(drive_type, drive_letter),
        }
        try:
            usage = shutil.disk_usage(path)
            payload.update({
                "size": usage.total, "free": usage.free,
                "total": usage.total, "used": usage.used,
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
                    dc = counters.get(key)
                    if dc:
                        payload["read_bytes"]  = getattr(dc, "read_bytes",  0)
                        payload["write_bytes"] = getattr(dc, "write_bytes", 0)
                        break
            except Exception:
                pass
        return payload

    def _connection_type(self, drive_type: str, letter: str) -> str:
        if drive_type == "network":   return "Network"
        if drive_type == "removable": return "USB"
        if drive_type == "cdrom":     return "Optical"
        if drive_type == "ramdisk":   return "RAM"
        mt = self._media_type_for_letter(letter)
        if mt == "SSD": return "SSD (SATA/NVMe)"
        if mt == "HDD": return "HDD (SATA)"
        return "Internal"

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
                ctypes.c_wchar_p(path), name_buf, len(name_buf),
                ctypes.byref(serial), ctypes.byref(max_comp),
                ctypes.byref(flags), fs_buf, len(fs_buf),
            )
            return name_buf.value.strip() if ok else ""
        except Exception:
            return ""

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
                "switch($u){ 'KB'{return [int64]($n*1KB)} 'MB'{return [int64]($n*1MB)} "
                " 'GB'{return [int64]($n*1GB)} 'TB'{return [int64]($n*1TB)} default{return [int64]$n} } "
                "} "
                "$items=@(); $index=0; "
                "$root=$shell.Namespace(17); "
                "foreach($item in $root.Items()){ "
                "  $p=$item.Path; "
                "  if($p -and $p -match '^[A-Z]:\\\\$'){ $index++; continue } "
                "  $type=[string]$item.Type; "
                "  $items+=[pscustomobject]@{"
                "    name=$item.Name; path=('shell:@'+$index); "
                "    is_dir=$true; drive=$true; drive_type='portable'; "
                "    device_type=$type; health='healthy'; removable=$true; "
                "    total=0; free=0; used=0; usage_percent=0 "
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
                    name             = item["name"]
                    device_type_hint = str(item.get("device_type", "")).lower()
                    is_camera  = "camera" in name.lower() or "ptp" in device_type_hint
                    is_android = (
                        "android" in name.lower()
                        or "phone" in device_type_hint
                        or "portable media player" in device_type_hint
                        or (not is_camera and "portable" in device_type_hint)
                    )
                    item["category"]        = "Android Device" if is_android else ("Camera (PTP)" if is_camera else "Portable Device")
                    item["display_name"]    = name
                    item["connection_type"] = "USB (MTP/PTP)"
                    devices.append(item)
        except Exception as exc:
            print(f"[portable_devices] {exc}")
        self._portable_cache    = devices
        self._portable_cache_ts = time.monotonic()
        return devices

    def network_shares_unmapped(self) -> list[dict]:
        if os.name != "nt":
            return []
        shares: list[dict] = []
        try:
            result = subprocess.run(["net", "use"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                for part in line.split():
                    if part.startswith("\\\\") and len(part) > 4:
                        unc  = part
                        name = unc.lstrip("\\").replace("\\", " › ")
                        shares.append({
                            "name": f"Network Share ({name})",
                            "display_name": f"Network Share ({name})",
                            "path": unc, "is_dir": True, "drive": True,
                            "drive_type": "network", "category": "Network Share",
                            "health": "healthy", "total": 0, "free": 0,
                            "used": 0, "usage_percent": 0, "removable": False,
                            "connection_type": "Network (SMB)", "volume_label": "",
                        })
        except Exception:
            pass
        for share in shares:
            try:
                usage = shutil.disk_usage(share["path"])
                share.update({
                    "total": usage.total, "free": usage.free, "used": usage.used,
                    "usage_percent": round((usage.used / usage.total) * 100, 1) if usage.total else 0,
                    "size": usage.total,
                })
            except OSError:
                share["health"] = "locked"
        return shares

    # ══════════════════════════════════════════════════════════════════════════
    # FILESYSTEM HELPERS
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
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            cpu_temp = None
            for _, entries in (temps or {}).items():
                for entry in entries:
                    if "cpu" in entry.label.lower() or entry.label == "":
                        cpu_temp = entry.current
                        break
                if cpu_temp:
                    break
        except Exception:
            cpu_temp = None
        return {
            "cpu":          psutil.cpu_percent(interval=None),
            "cpu_count":    psutil.cpu_count(logical=True),
            "cpu_temp":     cpu_temp,
            "ram":          psutil.virtual_memory().percent,
            "ram_total":    psutil.virtual_memory().total,
            "disk":         psutil.disk_usage(str(Path.home().anchor or "/")).percent,
            "battery":      battery.percent if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
            "network_sent": getattr(net, "bytes_sent", 0) if net else 0,
            "network_recv": getattr(net, "bytes_recv", 0) if net else 0,
            "processes":    len(psutil.pids()),
            "boot_time":    psutil.boot_time(),
        }

    def default_root(self) -> str:
        drives = self.drives()
        return drives[0]["path"] if drives else str(Path.home())

    def list_path(self, raw_path: str) -> dict:
        if str(raw_path or "").startswith("shell:"):
            return self.list_shell_path(raw_path)
        root    = Path(raw_path)
        entries = []
        try:
            items = list(root.iterdir())
        except PermissionError:
            return {"path": str(root), "entries": [], "error": "Permission denied"}
        for item in items:
            try:
                stat = item.stat()
                entries.append({
                    "name": item.name, "path": str(item),
                    "is_dir": item.is_dir(), "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except PermissionError:
                entries.append({"name": item.name, "path": str(item),
                                 "is_dir": item.is_dir(), "size": 0, "locked": True})
            except OSError:
                pass
        return {
            "path": str(root),
            "entries": sorted(entries, key=lambda r: (not r["is_dir"], r["name"].lower())),
        }

    def list_shell_path(self, raw_path: str) -> dict:
        segments      = [s for s in str(raw_path or "").removeprefix("shell:").split("/") if s]
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
            "$items=@(); $childIndex=0; "
            "foreach($item in $folder.Items()){ "
            "$childSegments=@($segments)+@('@'+$childIndex); "
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
            "  name=$item.Name; path=('shell:' + ($childSegments -join '/')); "
            "  is_dir=$item.IsFolder; size=0; size_text=$sizeText; "
            "  modified_text=$modifiedText; modified=$null; portable=$true; type=$item.Type"
            "}; $childIndex++ "
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
        unit   = match.group(2).upper()
        powers = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}
        return int(number * (1024 ** powers.get(unit, 0)))

    def upload_chunk(self, payload: dict) -> dict:
        directory = Path(payload.get("path") or self.default_root())
        directory.mkdir(parents=True, exist_ok=True)
        filename = Path(payload.get("name") or "upload.bin").name
        target   = directory / filename
        mode     = "ab" if int(payload.get("offset") or 0) else "wb"
        try:
            chunk = base64.b64decode(payload.get("chunk") or "", validate=True)
        except binascii.Error as exc:
            raise ValueError(f"Invalid upload chunk: {exc}") from exc
        with target.open(mode) as handle:
            handle.write(chunk)
        return {
            "path":     str(directory),
            "uploaded": str(target),
            "bytes":    target.stat().st_size,
            "complete": bool(payload.get("complete")),
        }

    def delete_path(self, raw_path: str) -> dict:
        path = Path(raw_path)
        if path.is_dir():
            raise PermissionError("Folder deletes are intentionally disabled.")
        path.unlink()
        return {"deleted": str(path)}

    def print_connection_tip(self, exc):
        message = str(exc).lower()
        if "timed out" not in message and "handshake" not in message:
            return
        parsed = urlparse(self.server)
        host   = parsed.hostname
        port   = parsed.port or (443 if parsed.scheme == "wss" else 80)
        if not host:
            return
        print(f"Checking server reachability at {host}:{port} …")
        try:
            with socket.create_connection((host, port), timeout=5):
                print("TCP port is reachable.")
        except OSError as tcp_exc:
            print(f"TCP port unreachable: {tcp_exc}.")


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL SESSION  (NEW v3)
# ══════════════════════════════════════════════════════════════════════════════

class TerminalSession:
    """Manages a single interactive shell subprocess."""

    def __init__(self, terminal_id: str, shell: str, cwd: str,
                 cols: int, rows: int, title: str):
        self.terminal_id = terminal_id
        self.shell       = shell
        self.cwd         = cwd
        self.cols        = cols
        self.rows        = rows
        self.title       = title
        self._proc: subprocess.Popen | None = None
        self._history: list[str]            = []
        self.exit_code: int | None          = None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self):
        env = os.environ.copy()
        env["TERM"]    = "xterm-256color"
        env["COLUMNS"] = str(self.cols)
        env["LINES"]   = str(self.rows)

        if os.name == "nt":
            # Windows: pipe-based (no PTY in stdlib)
            self._proc = subprocess.Popen(
                self.shell,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=env,
                shell=False,
                bufsize=0,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            # Unix: use a pseudo-terminal so shell behaves interactively
            import pty
            master_fd, slave_fd = pty.openpty()
            import fcntl, termios
            # Set terminal size
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            self._proc = subprocess.Popen(
                [self.shell],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=self.cwd,
                env=env,
                close_fds=True,
                preexec_fn=os.setsid,
            )
            os.close(slave_fd)
            self._master_fd = master_fd

    def read_output(self) -> str | None:
        """Blocking read — call from a thread."""
        if not self._proc:
            return None
        try:
            if os.name == "nt":
                data = self._proc.stdout.read(TERMINAL_OUTPUT_CHUNK)
            else:
                data = os.read(self._master_fd, TERMINAL_OUTPUT_CHUNK)
            if not data:
                self.exit_code = self._proc.wait()
                return None
            text = data.decode(errors="replace")
            self._history.append(text)
            if len(self._history) > TERMINAL_HISTORY_LIMIT:
                self._history = self._history[-TERMINAL_HISTORY_LIMIT:]
            return text
        except OSError:
            self.exit_code = self._proc.poll()
            return None

    def write_input(self, data: str):
        """Write data to the shell stdin. Call from a thread."""
        if not self._proc or not self.alive:
            return
        raw = data.encode("utf-8", errors="replace")
        if os.name == "nt":
            self._proc.stdin.write(raw)
            self._proc.stdin.flush()
        else:
            os.write(self._master_fd, raw)

    def resize(self, cols: int, rows: int):
        """Resize the terminal window. Call from a thread."""
        self.cols = cols
        self.rows = rows
        if os.name != "nt" and hasattr(self, "_master_fd"):
            import fcntl, termios
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            try:
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
                # Signal the child process group
                if self._proc and self._proc.pid:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGWINCH)
            except OSError:
                pass

    def kill(self):
        """Terminate the shell process."""
        if self._proc and self.alive:
            try:
                if os.name == "nt":
                    self._proc.terminate()
                else:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except OSError:
                pass
        if hasattr(self, "_master_fd"):
            with contextlib.suppress(OSError):
                os.close(self._master_fd)

    @property
    def history_text(self) -> str:
        return "".join(self._history)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ManageAI Remote Agent v3.0 — Advanced Edition")
    parser.add_argument("--server",    default="ws://127.0.0.1:8001", help="WebSocket server URL")
    parser.add_argument("--token",     required=True,                  help="Device token from ManageAI dashboard")
    parser.add_argument("--fps",       type=int, default=12,           help="Screen capture FPS (1-30)")
    parser.add_argument("--quality",   type=int, default=76,           help="JPEG quality (35-92)")
    parser.add_argument("--max-width", type=int, default=1600,         help="Max screen width in pixels")
    args = parser.parse_args()

    print(f"ManageAI Remote Agent v3.0 — Multi-Monitor · Terminal · Process Manager")
    print(f"Server : {args.server}")
    print(f"Token  : {args.token[:8]}…")
    print(f"Stream : {args.fps} FPS / Q{args.quality} / {args.max_width}px")
    print()

    asyncio.run(
        RemoteAgent(args.server, args.token, args.fps, args.quality, args.max_width).run()
    )


if __name__ == "__main__":
    main()