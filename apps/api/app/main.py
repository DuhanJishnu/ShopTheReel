"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import health
from app.api.v1 import auth, outfit, profile, reels, uploads
from app.core.deps import get_store
from app.core.errors import problem
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware

configure_logging()
log = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        await get_store().ensure_bucket()
    except Exception as exc:
        log.warning("storage ensure_bucket failed", error=str(exc))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ShopTheReel API", version="0.1.0", docs_url="/docs", lifespan=lifespan)
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(reels.router)
    app.include_router(outfit.router)
    app.include_router(uploads.router)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(request, 422, "Unprocessable Entity", str(exc.errors()))

    return app


app = create_app()
