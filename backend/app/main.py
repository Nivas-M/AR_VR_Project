"""FastAPI entrypoint for the TrueScale AR local backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def ensure_storage_dirs() -> None:
    """Create local runtime storage subdirectories if missing."""
    for subdir in ("uploads", "models", "jobs"):
        (settings.storage_dir / subdir).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare local storage directories on startup."""
    ensure_storage_dirs()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, object]:
    """Return service readiness, active engine, and storage directory state."""
    ensure_storage_dirs()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "default_engine": settings.default_engine,
        "storage_ready": settings.storage_dir.exists(),
    }
