"""API Middleware for correlation IDs and request context tracking.

PRD §14: Correlation IDs across API, webhook, worker, graph query, model call,
case, and audit events.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensures every request carries a correlation ID for end-to-end tracing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER) or f"corr_{uuid.uuid4().hex[:16]}"
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
