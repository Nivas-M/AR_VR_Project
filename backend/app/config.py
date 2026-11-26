"""Application configuration for TrueScale AR backend."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings for the local Photo-to-TrueScale-3D API."""

    app_name: str = "TrueScale AR API"
    app_version: str = "0.1.0"
    default_engine: str = "local_cpu"
    storage_dir: Path = BACKEND_DIR / "storage"
    max_image_size_px: int = 1024
    voxel_resolution: int = 68
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    cors_origin_regex: str = r"^https?://.*$"

    model_config = SettingsConfigDict(
        env_prefix="TRUESCALE_",
        extra="ignore",
    )


settings = Settings()
