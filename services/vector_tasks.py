from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import SessionLocal
from models import Recipe, RecipeIngredient
from services.embedding_provider import EmbeddingProviderError
from services.vector_service import upsert_recipe_embedding


def create_recipe_embedding_task(recipe_id: int) -> None:
    with SessionLocal() as db:
        recipe = db.execute(
            select(Recipe)
            .where(Recipe.id == recipe_id)
            .options(
                selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
                selectinload(Recipe.steps),
            )
        ).scalar_one_or_none()

        if not recipe:
            return

        try:
            upsert_recipe_embedding(db, recipe)
            db.commit()
        except EmbeddingProviderError:
            db.rollback()
