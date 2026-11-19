from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, channels, clips, sources
from app.core.security import require_api_key

app = FastAPI(title="OmniClip & Agentic YouTube Engine", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True,
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
