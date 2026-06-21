from contextvars import ContextVar

from starlette.requests import Request

current_request: ContextVar[Request | None] = ContextVar(
    "current_request", default=None
)
