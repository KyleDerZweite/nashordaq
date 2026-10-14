from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return (
        f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme in {"http", "https"} and parsed.netloc
        else ""
    )


class SessionRequestProtection(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response | None = None
        if request.url.path.startswith("/api/") and request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            origin = request.headers.get("origin")
            allowed = {_origin(str(request.url)), _origin(settings.public_url)}
            allowed.update(
                _origin(url.strip())
                for url in settings.cors_origins.split(",")
                if url.strip()
            )
            allowed.discard("")
            if (
                request.headers.get("X-Nashordaq-CSRF") != "1"
                or request.headers.get("Sec-Fetch-Site") == "cross-site"
                or (origin is not None and origin not in allowed)
            ):
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "Untrusted state-changing request"},
                )
        if response is None:
            response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
