import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, channels, clips, sources
from app.core import storage
from app.core.security import require_api_key

ORIGINS = ["http://localhost:3000"]


async def _ensure_bucket_with_retry(attempts: int = 30, delay: float = 2.0) -> None:
    """Object storage often finishes booting after the API; keep trying for ~1 minute."""
    log = logging.getLogger("uvicorn.error")
    for i in range(attempts):
        try:
            await asyncio.to_thread(storage.ensure_bucket, ORIGINS)
            log.info("object storage bucket ready")
            return
        except Exception as exc:
            if i == attempts - 1:
                log.error("could not ensure bucket after %d attempts: %s", attempts, exc)
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_ensure_bucket_with_retry())
    yield
    task.cancel()


app = FastAPI(title="OmniClip & Agentic YouTube Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

protected = [Depends(require_api_key)]
app.include_router(sources.router, dependencies=protected)
app.include_router(clips.router, dependencies=protected)
app.include_router(agents.router, dependencies=protected)
app.include_router(channels.router, dependencies=protected)
app.include_router(channels.oauth_router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
