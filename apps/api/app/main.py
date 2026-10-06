"""FastAPI application entrypoint."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import health
from app.api.v1 import auth, profile, uploads
from app.core.errors import problem
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware

configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(title="ShopTheReel API", version="0.1.0", docs_url="/docs")
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    app.include_router(uploads.router)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(request, 422, "Unprocessable Entity", str(exc.errors()))

    return app


app = create_app()
