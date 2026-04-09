from fastapi import FastAPI

from database import engine, SessionLocal, run_sqlite_migrations
from models import Base
from routers.recipes import router as recipes_router
from routers.menu import router as menu_router
from routers.imports import router as imports_router
from seed_data import seed_sample_data

app = FastAPI(title="AI Cooking Assistant MVP", version="1.0.0")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()
    with SessionLocal() as db:
        seed_sample_data(db)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(recipes_router)
app.include_router(menu_router)
app.include_router(imports_router)
