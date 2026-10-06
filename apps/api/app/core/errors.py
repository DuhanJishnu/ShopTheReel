"""RFC 7807 problem+json error helpers."""

from fastapi import Request
from fastapi.responses import JSONResponse


def problem(
    request: Request, status: int, title: str, detail: str, type_: str = "about:blank"
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": type_,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
            "request_id": getattr(request.state, "request_id", "-"),
        },
    )
