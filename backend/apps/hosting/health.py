import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlparse

import requests


ONLINE_STATUS_RANGE = range(200, 400)
OFFLINE_STATUS_RANGE = range(400, 600)


@dataclass
class HealthProbeResult:
    url: str
    final_url: str = ""
    status_code: int | None = None
    response_time_ms: int = 0
    online: bool = False
    slow: bool = False
    dns_ok: bool = False
    ssl_ok: bool = False
    ssl_expires_at: datetime | None = None
    redirect_chain: list[str] = field(default_factory=list)
    error: str = ""


def normalize_url(value):
    value = str(value or "").strip()
    if not value:
        return ""
    return value if value.startswith(("http://", "https://")) else f"https://{value}"


def probe_url(url, timeout=8, retries=2, slow_ms=2500):
    target = normalize_url(url)
    result = HealthProbeResult(url=target)
    if not target:
        result.error = "No URL configured."
        return result

    parsed = urlparse(target)
    host = parsed.hostname
    if not host:
        result.error = "Invalid URL."
        return result

    started = time.monotonic()
    try:
        socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        result.dns_ok = True
    except socket.gaierror as exc:
        result.response_time_ms = int((time.monotonic() - started) * 1000)
        result.error = f"DNS lookup failed: {exc}"
        return result

    if parsed.scheme == "https":
        ssl_result = _validate_ssl(host, parsed.port or 443, timeout)
        result.ssl_ok = ssl_result["ok"]
        result.ssl_expires_at = ssl_result.get("expires_at")
        if not result.ssl_ok:
            result.response_time_ms = int((time.monotonic() - started) * 1000)
            result.error = ssl_result.get("error") or "SSL validation failed."
            return result
    else:
        result.ssl_ok = True

    last_error = None
    for attempt in range(max(1, retries + 1)):
        try:
            response = requests.get(target, timeout=timeout, allow_redirects=True)
            result.response_time_ms = int((time.monotonic() - started) * 1000)
            result.status_code = response.status_code
            result.final_url = response.url
            result.redirect_chain = [item.url for item in response.history]
            result.online = response.status_code in ONLINE_STATUS_RANGE
            result.slow = result.online and result.response_time_ms > slow_ms
            result.error = "" if result.online else f"HTTP {response.status_code}"
            return result
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.35 * (attempt + 1))

    result.response_time_ms = int((time.monotonic() - started) * 1000)
    result.error = str(last_error or "Request failed.")
    return result


def _validate_ssl(host, port, timeout):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as wrapped:
                cert = wrapped.getpeercert()
        expires_at = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt_timezone.utc)
        return {"ok": expires_at > datetime.now(dt_timezone.utc), "expires_at": expires_at}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
