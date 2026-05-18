import secrets
import time
import base64
import hashlib
import hmac
import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import ApiKey


class AuthError(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


def _fernet():
    key = getattr(settings, "API_KEY_FERNET_KEY", "") or getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def generate_api_key(project_id=None, role=None, include_hash=False):
    plaintext_key = f"uce_{uuid.uuid4().hex}_{secrets.token_urlsafe(32)}"
    encrypted_key = _fernet().encrypt(plaintext_key.encode()).decode()
    prefix = plaintext_key[4:12]
    key_hash = make_password(plaintext_key)
    if include_hash:
        return plaintext_key, encrypted_key, prefix, key_hash
    if project_id is None and role is None:
        return plaintext_key, encrypted_key, prefix
    return {"plaintext": plaintext_key, "encrypted": encrypted_key, "prefix": prefix, "hash": key_hash}


def decrypt_api_key(encrypted):
    return _fernet().decrypt(encrypted.encode()).decode()


def get_rate_limit_key(api_key_id):
    return f"ratelimit:{api_key_id}:{int(time.time() // 60)}"


def validate_api_key(request, plaintext_key=None):
    if plaintext_key is None:
        plaintext_key = request
        request = None
    ip_address = _request_ip(request) if request is not None else None
    if not plaintext_key.startswith("uce_") or len(plaintext_key) <= 12:
        raise AuthError("Invalid API key")
    prefix = plaintext_key[4:12]
    for api_key in ApiKey.objects.select_related("project").filter(key_prefix=prefix, is_active=True):
        matched = False
        if api_key.key_hash:
            matched = check_password(plaintext_key, api_key.key_hash)
        if not matched and api_key.key_encrypted:
            try:
                stored_key = decrypt_api_key(api_key.key_encrypted)
                matched = hmac.compare_digest(stored_key, plaintext_key)
            except Exception:
                matched = False
        if not matched:
            continue
        if api_key.expires_at and api_key.expires_at <= timezone.now():
            raise AuthError("API key expired")
        whitelist = api_key.ip_whitelist or []
        if whitelist and ip_address not in whitelist:
            raise AuthError("IP address not allowed")
        cache_key = get_rate_limit_key(api_key.id)
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, 60)
            count = 1
        except Exception:
            count = 1
        if count > api_key.rate_limit_per_minute:
            raise RateLimitExceeded("Rate limit exceeded")
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at", "updated_at"])
        return api_key
    raise AuthError("Invalid API key")


def _request_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "") if request else ""
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or "127.0.0.1"
