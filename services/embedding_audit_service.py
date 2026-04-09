import os
from datetime import datetime, timezone
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import Recipe, RecipeEmbedding, RecipeIngredient
from services.embedding_provider import EmbeddingProviderError
from services.vector_service import upsert_recipe_embedding


_state_lock = Lock()
_state = {
    "last_run_at": None,
    "last_repaired_count": 0,
    "last_failed_count": 0,
}


def get_audit_config() -> dict:
    enabled = os.getenv("EMBEDDING_AUDIT_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    interval_seconds = int(os.getenv("EMBEDDING_AUDIT_INTERVAL_SECONDS", "600"))
    batch_size = int(os.getenv("EMBEDDING_AUDIT_BATCH_SIZE", "50"))
    initial_delay_seconds = int(os.getenv("EMBEDDING_AUDIT_INITIAL_DELAY_SECONDS", "10"))

    return {
        "enabled": enabled,
        "interval_seconds": max(10, interval_seconds),
        "batch_size": max(1, batch_size),
        "initial_delay_seconds": max(0, initial_delay_seconds),
    }


def _set_last_result(repaired_count: int, failed_count: int) -> None:
    with _state_lock:
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_repaired_count"] = repaired_count
        _state["last_failed_count"] = failed_count


def get_last_result() -> dict:
    with _state_lock:
        return dict(_state)


def get_embedding_counts(db: Session) -> tuple[int, int]:
    total_recipes = db.execute(select(func.count(Recipe.id))).scalar_one()
    total_embeddings = db.execute(select(func.count(RecipeEmbedding.id))).scalar_one()
    missing = max(0, int(total_recipes) - int(total_embeddings))
    return int(total_recipes), missing


def repair_missing_embeddings(db: Session, batch_size: int) -> dict:
    rows = db.execute(
        select(Recipe)
        .outerjoin(RecipeEmbedding, RecipeEmbedding.recipe_id == Recipe.id)
        .where(RecipeEmbedding.id.is_(None))
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
        )
        .order_by(Recipe.id.asc())
        .limit(batch_size)
    ).scalars().all()

    attempted = len(rows)
    repaired = 0
    failed = 0

    for recipe in rows:
        try:
            upsert_recipe_embedding(db, recipe)
            repaired += 1
        except EmbeddingProviderError:
            failed += 1

    db.commit()

    _, remaining_missing = get_embedding_counts(db)
    _set_last_result(repaired_count=repaired, failed_count=failed)

    return {
        "attempted_count": attempted,
        "repaired_count": repaired,
        "failed_count": failed,
        "remaining_missing": remaining_missing,
    }


def run_audit_once(batch_size: int) -> dict:
    from database import SessionLocal

    with SessionLocal() as db:
        return repair_missing_embeddings(db, batch_size=batch_size)
