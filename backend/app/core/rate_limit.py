import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings


class InMemoryRateLimiter:
    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str) -> tuple[bool, int]:
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            q = self._buckets[key]
            while q and q[0] < window_start:
                q.popleft()
            if len(q) >= self.requests_per_minute:
                retry_after = max(1, int(60 - (now - q[0])))
                return False, retry_after
            q.append(now)
            return True, 0


class RateLimitAndSecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            allowed, retry_after = self.limiter.is_allowed(f"{client_ip}:{path.split('/')[2] if len(path.split('/')) > 2 else 'api'}")
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please retry later.",
                        "code": "RATE_LIMIT_EXCEEDED",
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response
