import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit
from sqlalchemy import delete
from starlette.responses import JSONResponse
from .database import limits

BODY_LIMIT = 3 * 1024 * 1024 + 128 * 1024


class Problem(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1,
                            dklen=64, maxmem=64 * 1024 * 1024).hex()
    return f"scrypt-v1${salt}${digest}"


def verify_password(password, stored):
    try:
        version, salt, expected = stored.split("$")
        if version != "scrypt-v1" or len(salt) != 32 or len(expected) != 128:
            return False
        actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1,
                                dklen=64, maxmem=64 * 1024 * 1024).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def rate_limit(engine, peer, password_operation=False, namespace=None):
    """Atomic DB counter, deliberately ignores untrusted forwarded IP headers."""
    bucket = int(time.time()) // 900
    prefix = namespace or ("password" if password_operation else "write")
    key = prefix + ":" + hashlib.sha256(peer.encode()).hexdigest()
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    from sqlalchemy import case
    stmt = insert(limits).values(key=key, window=bucket, count=1)
    stmt = stmt.on_conflict_do_update(index_elements=[limits.c.key], set_={
        "window": bucket, "count": case((limits.c.window == bucket, limits.c.count + 1), else_=1)
    }).returning(limits.c.count)
    with engine.begin() as conn:
        count = conn.execute(stmt).scalar_one()
        conn.execute(delete(limits).where(limits.c.window < bucket - 1))
    if count > (10 if password_operation else 60):
        raise Problem("rate_limited", 429)


class BoundaryMiddleware:
    """Reject unauthorized origins and oversize bodies before multipart parsing."""
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, headers = scope["path"], dict(scope["headers"])

        async def reject(code, status):
            await JSONResponse({"error": code}, status_code=status)(scope, receive, secured_send)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"),
                    (b"cache-control", b"no-store")]
            await send(message)

        if self.settings.environment == "development":
            peer = (scope.get("client") or ("", 0))[0]
            host = headers.get(b"host", b"").decode("latin1")
            if peer not in {"127.0.0.1", "::1"} or urlsplit("//" + host).hostname not in {"localhost", "127.0.0.1", "::1"}:
                return await reject("local_development_only", 403)
        if (path.startswith('/api/admin') or path == '/admin' or path.startswith('/admin/')) and headers.get(b'x-vlabs-access-type', b'').strip().lower() == b'api':
            return await reject('admin_api_access_forbidden', 403)
        if path.startswith("/api/") or path == "/api":
            if (self.settings.environment == "production"
                    and self.settings.platform_access_mode != "sso"
                    and path not in {"/api/system/status", "/api/session", "/api/admin/session"}):
                # The SSO gateway, not emp_info or caller headers, must protect service access.
                return await reject("platform_auth_not_configured", 503)
            if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
                origins = [value for name, value in scope["headers"] if name.lower() == b"origin"]
                # An explicit service origin remains stable when a gateway rewrites
                # Host/scheme. Never trust a caller's forwarded headers as an allowlist.
                expected = self.settings.public_origin or (scope["scheme"] + "://" + headers.get(b"host", b"").decode("latin1"))
                if len(origins) != 1 or origins[0].decode("latin1") != expected:
                    return await reject("invalid_origin", 403)
                data = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    data.extend(message.get("body", b""))
                    if len(data) > BODY_LIMIT:
                        return await reject("too_large", 413)
                    if not message.get("more_body", False):
                        break
                delivered = False

                async def bounded_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(data), "more_body": False}
                    return await receive()
                return await self.app(scope, bounded_receive, secured_send)
        await self.app(scope, receive, secured_send)
