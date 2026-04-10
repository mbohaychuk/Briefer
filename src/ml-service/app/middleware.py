import hmac
import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates X-Api-Key header on all requests except /health."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        expected_key = os.environ.get("ML_SERVICE_API_KEY", "")
        if not expected_key:
            return await call_next(request)  # No key configured = no auth required

        provided_key = request.headers.get("X-Api-Key", "")
        if not provided_key or not hmac.compare_digest(provided_key, expected_key):
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        return await call_next(request)
