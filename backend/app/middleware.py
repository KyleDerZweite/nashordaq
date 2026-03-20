from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class DemoCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        token = getattr(request.state, "demo_session_token", None)
        if token is not None:
            max_age = int(settings.demo_session_ttl_hours * 3600)
            response.set_cookie(
                "nashordaq_demo_session",
                token,
                path="/",
                httponly=True,
                samesite="strict",
                max_age=max_age,
            )
        return response
