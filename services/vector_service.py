from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Recipe, RecipeEmbedding
from services.embedding_provider import get_embedding_provider, EmbeddingProviderError

def embed_text(text: str) -> list[float]:
    provider = get_embedding_provider()
    vectors = provider.embed_texts([text])
    if not vectors:
        raise EmbeddingProviderError("Embedding provider returned empty vector list.")
    return vectors[0]


def cosine_similarity(v1: Iterable[float], v2: Iterable[float]) -> float:
    return float(sum(a * b for a, b in zip(v1, v2)))


def build_recipe_source_text(recipe: Recipe) -> str:
    ingredient_tokens = " ".join(
        ri.ingredient.name for ri in recipe.recipe_ingredients if ri.ingredient
    )
    step_tokens = " ".join(step.instruction for step in recipe.steps)
    tag_tokens = " ".join(recipe.tags or [])

    parts = [
        recipe.name or "",
        recipe.description or "",
        recipe.main_ingredient or "",
        recipe.dish_type or "",
        recipe.cooking_method or "",
        recipe.difficulty or "",
        tag_tokens,
        ingredient_tokens,
        step_tokens,
    ]
    return " ".join(parts).strip()


def upsert_recipe_embedding(db: Session, recipe: Recipe) -> None:
    source_text = build_recipe_source_text(recipe)
    vector = embed_text(source_text)

    row = db.execute(
        select(RecipeEmbedding).where(RecipeEmbedding.recipe_id == recipe.id)
    ).scalar_one_or_none()

    if row:
        row.vector = vector
        row.source_text = source_text
    else:
        db.add(
            RecipeEmbedding(
                recipe_id=recipe.id,
                vector=vector,
                source_text=source_text,
            )
        )


def delete_recipe_embedding(db: Session, recipe_id: int) -> None:
    row = db.execute(
        select(RecipeEmbedding).where(RecipeEmbedding.recipe_id == recipe_id)
    ).scalar_one_or_none()
    if row:
        db.delete(row)
