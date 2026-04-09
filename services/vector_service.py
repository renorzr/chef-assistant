import hashlib
import math
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Recipe, RecipeEmbedding

VECTOR_DIM = 256


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_to_index(token: str, dim: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) % dim


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for token in tokens:
        idx = _hash_to_index(token, dim)
        vec[idx] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec

    return [v / norm for v in vec]


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
