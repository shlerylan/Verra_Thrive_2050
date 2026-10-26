import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.api.routes import router
from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import make_database


class RequestLimit:
    """Bound multipart bodies before the parser can spool an unbounded request."""
    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.limit:
                raise HTTPException(413)
            return message

        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine, sessions = make_database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="Thrive 2050 API", lifespan=lifespan)
    app.state.settings, app.state.sessions = settings, sessions
    app.add_middleware(RequestLimit, limit=settings.max_upload_bytes + 64 * 1024)
    app.include_router(router)

    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"error": {"code": "database_unavailable", "message": "The database is unavailable or migrations are pending."}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Check the required fields and identifier format."}})

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code == 413:
            return JSONResponse(status_code=413, content={"error": {"code": "upload_too_large", "message": "The request exceeds the configured upload limit."}})
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": "The request could not be processed."}})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logging.getLogger(__name__).error("Request failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "The request could not be completed. Please try again."}})

    return app


app = create_app()
