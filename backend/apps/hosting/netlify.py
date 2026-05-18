import time

import requests
from django.conf import settings
from django.core.cache import cache


class NetlifyApiError(Exception):
    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class NetlifyClient:
    base_url = "https://api.netlify.com/api/v1"

    def __init__(self, token=None):
        self.token = token or getattr(settings, "NETLIFY_API_TOKEN", "")
        if not self.token:
            raise NetlifyApiError("NETLIFY_API_TOKEN is not configured.")

    def request(self, method, path, params=None, json=None, retries=3, timeout=20):
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        last_error = None
        for attempt in range(retries):
            try:
                response = requests.request(method, url, headers=headers, params=params, json=json, timeout=timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                if response.status_code >= 400:
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = {"detail": response.text}
                    message = payload.get("message") or payload.get("error") or payload.get("detail") or "Netlify API request failed."
                    raise NetlifyApiError(message, response.status_code, payload)
                if response.status_code == 204:
                    return {}
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
        raise NetlifyApiError(str(last_error or "Netlify API request failed."))

    def list_sites(self):
        return self.request("GET", "/sites")

    def list_deploys(self, sites=None, limit=30):
        try:
            return self.request("GET", "/deploys", params={"per_page": limit})
        except NetlifyApiError as exc:
            if exc.status_code not in {404, 405}:
                raise

        deploys = []
        for site in (sites or [])[:20]:
            site_id = site.get("id")
            if not site_id:
                continue
            try:
                deploys.extend(self.request("GET", f"/sites/{site_id}/deploys", params={"per_page": max(1, min(limit, 20))}))
            except NetlifyApiError:
                continue
        return sorted(deploys, key=lambda item: item.get("created_at") or item.get("updated_at") or "", reverse=True)[:limit]

    def trigger_build(self, site_id):
        return self.request("POST", f"/sites/{site_id}/builds")


def get_netlify_status(force=False):
    cache_key = "netlify:status"
    if not force:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    client = NetlifyClient()
    sites = client.list_sites()
    deploys = client.list_deploys(sites=sites, limit=40)
    payload = build_netlify_payload(sites, deploys)
    _cache_set(cache_key, payload, 25)
    return payload


def build_netlify_payload(sites, deploys):
    sites = sites or []
    deploys = deploys or []
    failed_deploys = [deploy for deploy in deploys if str(deploy.get("state", "")).lower() == "error"]
    success_deploys = [deploy for deploy in deploys if str(deploy.get("state", "")).lower() in {"ready", "uploaded"}]
    building_deploys = [deploy for deploy in deploys if str(deploy.get("state", "")).lower() in {"building", "enqueued", "processing"}]
    latest_deploy = deploys[0] if deploys else {}
    total_considered = len(success_deploys) + len(failed_deploys)
    uptime = round((len(success_deploys) / total_considered) * 100) if total_considered else 100
    has_error = bool(failed_deploys and latest_deploy in failed_deploys)

    return {
        "active": len([site for site in sites if site.get("published_deploy")]),
        "failed": len(failed_deploys),
        "uptime": f"{uptime}%",
        "uptimeValue": uptime,
        "lastDeploy": _first_present(latest_deploy, ["created_at", "updated_at", "published_at"], ""),
        "lastDeployLabel": _relative_time(_first_present(latest_deploy, ["created_at", "updated_at", "published_at"], "")),
        "status": "Error" if has_error else "Active",
        "indicator": "Error" if has_error else "Building" if building_deploys else "Live",
        "sites": [_site_summary(site) for site in sites[:30]],
        "deploys": [_deploy_summary(deploy) for deploy in deploys[:30]],
        "logsPreview": [_log_preview(deploy) for deploy in deploys[:8]],
    }


def _site_summary(site):
    published = site.get("published_deploy") or {}
    return {
        "id": site.get("id"),
        "name": site.get("name") or site.get("custom_domain") or site.get("default_domain"),
        "url": site.get("ssl_url") or site.get("url"),
        "adminUrl": site.get("admin_url"),
        "state": published.get("state") or ("published" if published else "unknown"),
        "updatedAt": site.get("updated_at"),
    }


def _deploy_summary(deploy):
    summary = deploy.get("summary") if isinstance(deploy.get("summary"), dict) else {}
    return {
        "id": deploy.get("id"),
        "siteId": deploy.get("site_id"),
        "siteName": deploy.get("name") or deploy.get("site_name"),
        "state": deploy.get("state") or "unknown",
        "url": deploy.get("deploy_ssl_url") or deploy.get("ssl_url") or deploy.get("url"),
        "createdAt": deploy.get("created_at"),
        "updatedAt": deploy.get("updated_at"),
        "title": deploy.get("title") or deploy.get("branch") or "Deployment",
        "errorMessage": deploy.get("error_message") or summary.get("message") or "",
    }


def _log_preview(deploy):
    state = deploy.get("state") or "unknown"
    title = deploy.get("title") or deploy.get("name") or deploy.get("site_name") or "Netlify deployment"
    return {
        "id": deploy.get("id"),
        "level": "error" if state == "error" else "info",
        "title": title,
        "message": deploy.get("error_message") or f"{state.title()} deploy at {_relative_time(deploy.get('created_at'))}",
    }


def _first_present(source, keys, default=None):
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return default


def _relative_time(value):
    if not value:
        return "No deploys yet"
    try:
        from django.utils.dateparse import parse_datetime
        from django.utils.timesince import timesince
        from django.utils import timezone

        parsed = parse_datetime(value)
        if not parsed:
            return value
        return f"{timesince(parsed, timezone.now()).split(',')[0]} ago"
    except Exception:
        return value


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        pass
