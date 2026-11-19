from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://omni:omni@localhost:5432/omniclip"
    sync_database_url: str = "postgresql+psycopg2://omni:omni@localhost:5432/omniclip"
    redis_url: str = "redis://localhost:6379/0"
    api_key: str = "change-me-internal-team-key"

    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_bucket: str = "omniclip"
    aws_region: str = "us-east-1"

    llm_model: str = "claude-opus-5-5"
    llm_fast_model: str = "claude-haiku-5-5"
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    ffmpeg_gpu: bool = False
    render_width: int = 1080
    render_height: int = 1920
    work_dir: str = "/tmp/omniclip"
    face_model_path: str = "/models/face_detection_yunet_2023mar.onnx"

    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8000/api/channels/oauth/callback"
    youtube_api_key: str = ""
    token_encryption_key: str = ""

    # Clip-length bounds for Shorts (YouTube Shorts allow up to 180s; 20-60s performs best)
    clip_min_sec: float = 15.0
    clip_max_sec: float = 75.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
