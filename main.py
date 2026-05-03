import asyncio
from email.utils import formatdate
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import SessionLocal, cleanup_placeholder_media
from routers.recipes import router as recipes_router
from routers.chat import router as chat_router
from routers.menu import router as menu_router
from routers.menus import router as menus_router
from routers.meal_plans import router as meal_plans_router
from routers.imports import router as imports_router
from routers.admin import router as admin_router
from routers.media import router as media_router
from seed_data import seed_sample_data
from services.embedding_audit_service import get_audit_config, run_audit_once

app = FastAPI(title="AI Cooking Assistant MVP", version="1.0.0")
FRONTEND_DIST_DIR = Path(__file__).parent / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
UPLOADS_DIR = Path(__file__).parent / "uploads"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
INDEX_CACHE_CONTROL = "no-cache, must-revalidate"

_audit_stop_event: asyncio.Event | None = None
_audit_task: asyncio.Task | None = None


async def _embedding_audit_loop(stop_event: asyncio.Event) -> None:
    cfg = get_audit_config()
    if not cfg["enabled"]:
        return

    initial_delay = cfg["initial_delay_seconds"]
    if initial_delay > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
            return
        except asyncio.TimeoutError:
            pass

    while not stop_event.is_set():
        try:
            await asyncio.to_thread(run_audit_once, cfg["batch_size"])
        except Exception:
            pass

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=cfg["interval_seconds"])
        except asyncio.TimeoutError:
            continue


@app.on_event("startup")
async def on_startup():
    cleanup_placeholder_media()
    with SessionLocal() as db:
        seed_sample_data(db)

    global _audit_stop_event, _audit_task
    _audit_stop_event = asyncio.Event()
    _audit_task = asyncio.create_task(_embedding_audit_loop(_audit_stop_event))


@app.on_event("shutdown")
async def on_shutdown():
    global _audit_stop_event, _audit_task
    if _audit_stop_event is not None:
        _audit_stop_event.set()
    if _audit_task is not None:
        try:
            await _audit_task
        except Exception:
            pass

    _audit_stop_event = None
    _audit_task = None


@app.get("/health")
def health_check():
    return {"status": "ok"}


def _register_api_routers(prefix: str = "") -> None:
    app.include_router(recipes_router, prefix=prefix)
    app.include_router(chat_router, prefix=prefix)
    app.include_router(menu_router, prefix=prefix)
    app.include_router(menus_router, prefix=prefix)
    app.include_router(meal_plans_router, prefix=prefix)
    app.include_router(imports_router, prefix=prefix)
    app.include_router(admin_router, prefix=prefix)
    app.include_router(media_router, prefix=prefix)


_register_api_routers()
_register_api_routers("/api")


class CacheControlStaticFiles(StaticFiles):
    def __init__(self, *args, cache_control: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_control = cache_control

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if self.cache_control and response.status_code == 200:
            response.headers["Cache-Control"] = self.cache_control
        return response


def frontend_index_response():
    index_path = FRONTEND_DIST_DIR / "index.html"
    response = FileResponse(index_path)
    response.headers["Cache-Control"] = INDEX_CACHE_CONTROL
    try:
        stat = index_path.stat()
        response.headers["Last-Modified"] = formatdate(stat.st_mtime, usegmt=True)
    except OSError:
        pass
    return response


if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", CacheControlStaticFiles(directory=str(FRONTEND_ASSETS_DIR), cache_control=ASSET_CACHE_CONTROL), name="frontend-assets")

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/", include_in_schema=False)
def serve_frontend_index():
    if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
        return frontend_index_response()
    return {"status": "frontend_not_built"}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_app(full_path: str):
    reserved_prefixes = ("api/", "docs", "openapi.json", "redoc", "assets/", "uploads/")
    if full_path == "health" or full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")

    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.exists():
        return frontend_index_response()
    return {"status": "frontend_not_built"}
