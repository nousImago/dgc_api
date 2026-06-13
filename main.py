from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from config import settings
from integrations.db.engine import engine
from observability.exceptions import register_exception_handlers
from observability.logging import configure_logging
from observability.middleware import AccessLogMiddleware, RequestIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(AccessLogMiddleware)

register_exception_handlers(app)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness probe target. No DB access — must stay cheap."""
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    """Public smoke-test endpoint. No auth, no DB. Verifies routing end-to-end."""
    return {
        "message": "Hello from DGC API",
        "service": settings.APP_NAME,
        "env": "debug" if settings.DEBUG else "production",
    }
