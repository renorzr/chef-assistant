import asyncio

from fastapi import FastAPI

from database import engine, SessionLocal, run_sqlite_migrations
from models import Base
from routers.recipes import router as recipes_router
from routers.menu import router as menu_router
from routers.imports import router as imports_router
from routers.admin import router as admin_router
from seed_data import seed_sample_data
from services.embedding_audit_service import get_audit_config, run_audit_once

app = FastAPI(title="AI Cooking Assistant MVP", version="1.0.0")

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
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()
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


app.include_router(recipes_router)
app.include_router(menu_router)
app.include_router(imports_router)
app.include_router(admin_router)
