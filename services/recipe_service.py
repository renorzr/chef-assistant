import re
from collections import Counter
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import Recipe, Ingredient, RecipeIngredient, RecipeStep, RecipeMedia, RecipeEmbedding
from schemas import (
    RecipeCreate,
    RecipeRead,
    RecipeIngredientRead,
    RecipeStepRead,
    RecipeMediaRead,
    VectorSearchRequest,
    VectorSearchResponse,
    VectorSearchResult,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResult,
    EmbeddingReindexResponse,
)
from services.vector_service import (
    embed_text,
    cosine_similarity,
    upsert_recipe_embedding,
    delete_recipe_embedding,
)
from services.embedding_provider import EmbeddingProviderError
from services.ingredient_service import normalize_ingredient_entry


def _normalize_text(value: str) -> str:
    return value.strip().lower()


def _tokenize_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _keyword_similarity(query: str, recipe: Recipe) -> float:
    query_tokens = _tokenize_text(query)
    if not query_tokens:
        return 0.0

    recipe_tokens: list[str] = []
    recipe_tokens.extend(_tokenize_text(recipe.name))
    recipe_tokens.extend(_tokenize_text(recipe.description or ""))
    recipe_tokens.extend(_tokenize_text(recipe.main_ingredient or ""))
    recipe_tokens.extend(_tokenize_text(recipe.dish_type or ""))
    recipe_tokens.extend(_tokenize_text(recipe.cooking_method or ""))
    recipe_tokens.extend(_tokenize_text(" ".join(recipe.tags or [])))
    recipe_tokens.extend(
        _tokenize_text(" ".join(ri.ingredient.name for ri in recipe.recipe_ingredients if ri.ingredient))
    )

    if not recipe_tokens:
        return 0.0

    q_count = Counter(query_tokens)
    r_count = Counter(recipe_tokens)

    intersection = sum(min(q_count[t], r_count[t]) for t in q_count)
    q_norm = sum(v * v for v in q_count.values()) ** 0.5
    r_norm = sum(v * v for v in r_count.values()) ** 0.5
    if q_norm == 0 or r_norm == 0:
        return 0.0

    return float(intersection / (q_norm * r_norm))


def _passes_recipe_filters(recipe: Recipe, max_cook_time_minutes: int | None, difficulty: str | None, tags: set[str]) -> bool:
    if difficulty and (recipe.difficulty or "").lower() != difficulty:
        return False
    if max_cook_time_minutes and recipe.cook_time_minutes > max_cook_time_minutes:
        return False
    if tags:
        recipe_tags = {t.strip().lower() for t in (recipe.tags or [])}
        if not tags.issubset(recipe_tags):
            return False
    return True


def get_or_create_ingredient(db: Session, name: str) -> Ingredient:
    normalized, _, _ = normalize_ingredient_entry(name)
    if not normalized:
        raise ValueError("Ingredient name cannot be empty.")
    existing = db.execute(
        select(Ingredient).where(Ingredient.name == normalized)
    ).scalar_one_or_none()

    if existing:
        return existing

    ingredient = Ingredient(name=normalized)
    db.add(ingredient)
    db.flush()
    return ingredient


def _to_recipe_read(recipe: Recipe) -> RecipeRead:
    ingredients = [
        RecipeIngredientRead(
            id=ri.id,
            ingredient_id=ri.ingredient_id,
            name=ri.ingredient.name,
            amount=ri.amount,
            unit=ri.unit,
            note=ri.note,
            optional=bool(ri.optional),
            is_main=bool(ri.is_main),
        )
        for ri in recipe.recipe_ingredients
    ]

    steps = [
        RecipeStepRead(
            id=step.id,
            step_order=step.step_order,
            instruction=step.instruction,
            image_url=step.image_url,
        )
        for step in sorted(recipe.steps, key=lambda x: x.step_order)
    ]

    media = [
        RecipeMediaRead(
            id=m.id,
            media_type=m.media_type,
            url=m.url,
        )
        for m in recipe.media
    ]

    return RecipeRead(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        cook_time_minutes=recipe.cook_time_minutes,
        difficulty=recipe.difficulty,
        tags=recipe.tags or [],
        source_type=recipe.source_type,
        source_url=recipe.source_url,
        cover_image_url=recipe.cover_image_url,
        main_ingredient=recipe.main_ingredient,
        dish_type=recipe.dish_type,
        cooking_method=recipe.cooking_method,
        ingredients=ingredients,
        steps=steps,
        media=media,
    )


def create_recipe(db: Session, payload: RecipeCreate) -> RecipeRead:
    recipe = Recipe(
        name=payload.name.strip(),
        description=payload.description,
        cook_time_minutes=payload.cook_time_minutes,
        difficulty=payload.difficulty.lower().strip(),
        tags=[t.strip().lower() for t in payload.tags],
        source_type=payload.source_type.lower().strip(),
        source_url=payload.source_url,
        cover_image_url=payload.cover_image_url,
        main_ingredient=payload.main_ingredient.lower().strip() if payload.main_ingredient else None,
        dish_type=payload.dish_type.lower().strip(),
        cooking_method=payload.cooking_method.lower().strip(),
    )
    db.add(recipe)
    db.flush()

    chosen_main = recipe.main_ingredient

    for item in payload.ingredients:
        normalized_name, normalized_amount, normalized_unit = normalize_ingredient_entry(item.name, item.amount, item.unit)
        if not normalized_name:
            continue
        ing = get_or_create_ingredient(db, normalized_name)
        link = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ing.id,
            amount=normalized_amount,
            unit=normalized_unit,
            note=item.note.strip() if item.note else None,
            optional=1 if item.optional else 0,
            is_main=1 if item.is_main else 0,
        )
        db.add(link)

        if not chosen_main and item.is_main:
            chosen_main = ing.name

    if not chosen_main and payload.ingredients:
        chosen_main, _, _ = normalize_ingredient_entry(payload.ingredients[0].name, payload.ingredients[0].amount, payload.ingredients[0].unit)

    recipe.main_ingredient = chosen_main

    ordered_steps = sorted(payload.steps, key=lambda s: s.step_order)
    for step in ordered_steps:
        db.add(
            RecipeStep(
                recipe_id=recipe.id,
                step_order=step.step_order,
                instruction=step.instruction.strip(),
                image_url=step.image_url,
            )
        )

    for m in payload.media:
        db.add(
            RecipeMedia(
                recipe_id=recipe.id,
                media_type=m.media_type.lower().strip(),
                url=m.url.strip(),
            )
        )

    recipe = db.execute(
        select(Recipe)
        .where(Recipe.id == recipe.id)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.media),
        )
    ).scalar_one()

    db.commit()

    return _to_recipe_read(recipe)


def _load_recipe_with_relations(db: Session, recipe_id: int) -> Recipe | None:
    return db.execute(
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.media),
        )
    ).scalar_one_or_none()


def update_recipe(db: Session, recipe_id: int, payload: RecipeCreate) -> RecipeRead:
    recipe = _load_recipe_with_relations(db, recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    recipe.name = payload.name.strip()
    recipe.description = payload.description
    recipe.cook_time_minutes = payload.cook_time_minutes
    recipe.difficulty = payload.difficulty.lower().strip()
    recipe.tags = [t.strip().lower() for t in payload.tags]
    recipe.source_type = payload.source_type.lower().strip()
    recipe.source_url = payload.source_url
    recipe.cover_image_url = payload.cover_image_url
    recipe.main_ingredient = payload.main_ingredient.lower().strip() if payload.main_ingredient else None
    recipe.dish_type = payload.dish_type.lower().strip()
    recipe.cooking_method = payload.cooking_method.lower().strip()

    recipe.recipe_ingredients.clear()
    recipe.steps.clear()
    recipe.media.clear()
    db.flush()

    chosen_main = recipe.main_ingredient

    for item in payload.ingredients:
        normalized_name, normalized_amount, normalized_unit = normalize_ingredient_entry(item.name, item.amount, item.unit)
        if not normalized_name:
            continue
        ing = get_or_create_ingredient(db, normalized_name)
        recipe.recipe_ingredients.append(
            RecipeIngredient(
                ingredient_id=ing.id,
                amount=normalized_amount,
                unit=normalized_unit,
                note=item.note.strip() if item.note else None,
                optional=1 if item.optional else 0,
                is_main=1 if item.is_main else 0,
            )
        )

        if not chosen_main and item.is_main:
            chosen_main = ing.name

    if not chosen_main and payload.ingredients:
        chosen_main, _, _ = normalize_ingredient_entry(payload.ingredients[0].name, payload.ingredients[0].amount, payload.ingredients[0].unit)

    recipe.main_ingredient = chosen_main

    for step in sorted(payload.steps, key=lambda s: s.step_order):
        recipe.steps.append(
            RecipeStep(
                step_order=step.step_order,
                instruction=step.instruction.strip(),
                image_url=step.image_url,
            )
        )

    for m in payload.media:
        recipe.media.append(
            RecipeMedia(
                media_type=m.media_type.lower().strip(),
                url=m.url.strip(),
            )
        )

    # Remove stale embedding immediately; async task/audit will rebuild with new content.
    delete_recipe_embedding(db, recipe_id)

    db.commit()

    refreshed = _load_recipe_with_relations(db, recipe_id)
    return _to_recipe_read(refreshed)


def delete_recipe(db: Session, recipe_id: int) -> bool:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        return False

    delete_recipe_embedding(db, recipe_id)
    db.delete(recipe)
    db.commit()
    return True


def list_recipes(db: Session, skip: int = 0, limit: int = 100) -> List[RecipeRead]:
    rows = db.execute(
        select(Recipe)
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.media),
        )
        .order_by(Recipe.id.asc())
    ).scalars().all()

    return [_to_recipe_read(r) for r in rows]


def get_recipe_by_id(db: Session, recipe_id: int) -> RecipeRead | None:
    recipe = _load_recipe_with_relations(db, recipe_id)
    if not recipe:
        return None
    return _to_recipe_read(recipe)


def normalize_existing_ingredients(db: Session) -> None:
    def merge_recipe_ingredient_rows(target_row: RecipeIngredient, source_row: RecipeIngredient) -> bool:
        merged = False
        if not target_row.amount and source_row.amount:
            target_row.amount = source_row.amount
            merged = True
        if not target_row.unit and source_row.unit:
            target_row.unit = source_row.unit
            merged = True
        if not target_row.is_main and source_row.is_main:
            target_row.is_main = source_row.is_main
            merged = True
        if not target_row.note and source_row.note:
            target_row.note = source_row.note
            merged = True
        if not target_row.optional and source_row.optional:
            target_row.optional = source_row.optional
            merged = True
        return merged

    rows = db.execute(
        select(RecipeIngredient)
        .options(selectinload(RecipeIngredient.ingredient))
        .order_by(RecipeIngredient.id.asc())
    ).scalars().all()

    changed = False
    grouped_rows: dict[tuple[int, int], RecipeIngredient] = {}
    for row in rows:
        if not row.ingredient:
            continue

        normalized_name, normalized_amount, normalized_unit = normalize_ingredient_entry(
            row.ingredient.name,
            row.amount,
            row.unit,
        )
        if not normalized_name:
            continue

        target = get_or_create_ingredient(db, normalized_name)
        group_key = (row.recipe_id, target.id)
        survivor = grouped_rows.get(group_key)

        if survivor and survivor.id != row.id:
            if merge_recipe_ingredient_rows(survivor, row):
                changed = True
            db.delete(row)
            changed = True
            continue

        duplicate = db.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == row.recipe_id,
                RecipeIngredient.ingredient_id == target.id,
                RecipeIngredient.id != row.id,
            )
        ).scalar_one_or_none()

        if duplicate:
            if merge_recipe_ingredient_rows(duplicate, row):
                changed = True
            if not duplicate.amount and normalized_amount:
                duplicate.amount = normalized_amount
                changed = True
            if not duplicate.unit and normalized_unit:
                duplicate.unit = normalized_unit
                changed = True
            grouped_rows[group_key] = duplicate
            db.delete(row)
            changed = True
            continue

        grouped_rows[group_key] = row

        if row.ingredient_id != target.id:
            row.ingredient_id = target.id
            changed = True
        if row.amount != normalized_amount:
            row.amount = normalized_amount
            changed = True
        if row.unit != normalized_unit:
            row.unit = normalized_unit
            changed = True
        if row.note and row.note.strip() == row.ingredient.name:
            row.note = None
            changed = True

    db.flush()

    orphan_ids = db.execute(
        select(Ingredient.id)
        .outerjoin(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(RecipeIngredient.id.is_(None))
    ).scalars().all()
    for ingredient_id in orphan_ids:
        ingredient = db.get(Ingredient, ingredient_id)
        if ingredient:
            db.delete(ingredient)
            changed = True

    if changed:
        db.commit()


def search_recipes_by_vector(db: Session, payload: VectorSearchRequest) -> VectorSearchResponse:
    try:
        query_vec = embed_text(payload.query)
    except EmbeddingProviderError as exc:
        raise ValueError(f"Vector search unavailable: {exc}") from exc

    rows = db.execute(
        select(Recipe)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.media),
            selectinload(Recipe.embedding),
        )
        .order_by(Recipe.id.asc())
    ).scalars().all()

    requested_tags = {t.strip().lower() for t in payload.tags if t and t.strip()}
    requested_difficulty = payload.difficulty.strip().lower() if payload.difficulty else None

    scored: list[tuple[float, RecipeRead]] = []

    for recipe in rows:
        if not _passes_recipe_filters(
            recipe,
            max_cook_time_minutes=payload.max_cook_time_minutes,
            difficulty=requested_difficulty,
            tags=requested_tags,
        ):
            continue

        embedding_vector = recipe.embedding.vector if recipe.embedding else None
        if embedding_vector is None:
            try:
                upsert_recipe_embedding(db, recipe)
            except EmbeddingProviderError as exc:
                raise ValueError(f"Vector search unavailable: {exc}") from exc
            db.flush()
            embedding_row = db.execute(
                select(RecipeEmbedding).where(RecipeEmbedding.recipe_id == recipe.id)
            ).scalar_one()
            embedding_vector = embedding_row.vector

        score = cosine_similarity(query_vec, embedding_vector)
        scored.append((score, _to_recipe_read(recipe)))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: payload.top_k]

    return VectorSearchResponse(
        query=payload.query,
        results=[
            VectorSearchResult(
                recipe=recipe,
                score=round(score, 4),
            )
            for score, recipe in top
        ],
    )


def search_recipes_hybrid(db: Session, payload: HybridSearchRequest) -> HybridSearchResponse:
    try:
        query_vec = embed_text(payload.query)
    except EmbeddingProviderError as exc:
        raise ValueError(f"Hybrid search unavailable: {exc}") from exc

    rows = db.execute(
        select(Recipe)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.media),
            selectinload(Recipe.embedding),
        )
        .order_by(Recipe.id.asc())
    ).scalars().all()

    requested_tags = {t.strip().lower() for t in payload.tags if t and t.strip()}
    requested_difficulty = payload.difficulty.strip().lower() if payload.difficulty else None

    hybrid_scored: list[tuple[float, float, float, RecipeRead]] = []

    for recipe in rows:
        if not _passes_recipe_filters(
            recipe,
            max_cook_time_minutes=payload.max_cook_time_minutes,
            difficulty=requested_difficulty,
            tags=requested_tags,
        ):
            continue

        embedding_vector = recipe.embedding.vector if recipe.embedding else None
        if embedding_vector is None:
            try:
                upsert_recipe_embedding(db, recipe)
            except EmbeddingProviderError as exc:
                raise ValueError(f"Hybrid search unavailable: {exc}") from exc
            db.flush()
            embedding_row = db.execute(
                select(RecipeEmbedding).where(RecipeEmbedding.recipe_id == recipe.id)
            ).scalar_one()
            embedding_vector = embedding_row.vector

        semantic_score = cosine_similarity(query_vec, embedding_vector)
        keyword_score = _keyword_similarity(payload.query, recipe)
        final_score = payload.semantic_weight * semantic_score + (1.0 - payload.semantic_weight) * keyword_score

        hybrid_scored.append((final_score, semantic_score, keyword_score, _to_recipe_read(recipe)))

    hybrid_scored.sort(key=lambda x: x[0], reverse=True)
    top = hybrid_scored[: payload.top_k]

    return HybridSearchResponse(
        query=payload.query,
        semantic_weight=payload.semantic_weight,
        results=[
            HybridSearchResult(
                recipe=recipe,
                score=round(score, 4),
                semantic_score=round(semantic_score, 4),
                keyword_score=round(keyword_score, 4),
            )
            for score, semantic_score, keyword_score, recipe in top
        ],
    )


def reindex_recipe_embeddings(db: Session, only_missing: bool = False) -> EmbeddingReindexResponse:
    rows = db.execute(
        select(Recipe)
        .options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient),
            selectinload(Recipe.steps),
            selectinload(Recipe.embedding),
        )
        .order_by(Recipe.id.asc())
    ).scalars().all()

    total = len(rows)
    reindexed = 0
    skipped = 0
    failed = 0

    for recipe in rows:
        if only_missing and recipe.embedding is not None:
            skipped += 1
            continue

        try:
            upsert_recipe_embedding(db, recipe)
            reindexed += 1
        except EmbeddingProviderError:
            failed += 1

    db.commit()

    if failed > 0:
        message = "Reindex completed with failures. Check embedding provider configuration and availability."
    else:
        message = "Reindex completed successfully."

    return EmbeddingReindexResponse(
        total_recipes=total,
        reindexed_count=reindexed,
        skipped_count=skipped,
        failed_count=failed,
        message=message,
    )
