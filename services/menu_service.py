from itertools import combinations
from typing import List, Tuple, Dict, Set
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import Recipe, RecipeIngredient
from schemas import MenuGenerateRequest, MenuGenerateResponse, MenuDish


def _norm_set(items: List[str]) -> Set[str]:
    return {x.strip().lower() for x in items if x and x.strip()}


def _recipe_text_blob(recipe: Recipe) -> str:
    fields = [
        recipe.name or "",
        recipe.main_ingredient or "",
        recipe.dish_type or "",
        recipe.cooking_method or "",
        " ".join(recipe.tags or []),
        " ".join(ri.ingredient.name for ri in recipe.recipe_ingredients if ri.ingredient),
    ]
    return " ".join(fields).lower()


def _matches_preferences(recipe: Recipe, prefs: Set[str]) -> bool:
    if not prefs:
        return True
    blob = _recipe_text_blob(recipe)
    return any(p in blob for p in prefs)


def _score_combo(
    combo: Tuple[Recipe, ...],
    available_ingredients: Set[str],
    constraints: Set[str],
    preferences: Set[str],
    candidate_has_meat: bool,
    candidate_has_veg: bool,
) -> Tuple[float, Dict[str, float], List[str]]:
    notes: List[str] = []

    total_ings = 0
    matched_ings = 0
    for recipe in combo:
        for ri in recipe.recipe_ingredients:
            total_ings += 1
            ing_name = ri.ingredient.name.lower()
            if ing_name in available_ingredients:
                matched_ings += 1

    if total_ings == 0:
        ingredient_score = 0.0
    elif available_ingredients:
        ingredient_score = 40.0 * (matched_ings / total_ings)
    else:
        ingredient_score = 20.0

    main_ingredients = [r.main_ingredient.lower() for r in combo if r.main_ingredient]
    cooking_methods = [r.cooking_method.lower() for r in combo if r.cooking_method]

    unique_main = len(set(main_ingredients)) if main_ingredients else 1
    unique_method = len(set(cooking_methods)) if cooking_methods else 1

    main_div_score = 10.0 * (unique_main / max(1, len(combo)))
    method_div_score = 10.0 * (unique_method / max(1, len(combo)))

    has_meat = any((r.dish_type or "").lower() == "meat" for r in combo)
    has_veg = any((r.dish_type or "").lower() == "vegetable" for r in combo)

    mix_score = 0.0
    if candidate_has_meat and candidate_has_veg:
        if has_meat and has_veg:
            mix_score = 10.0
            notes.append("Includes both meat and vegetable dishes.")
        else:
            mix_score = -8.0
            notes.append("Could not balance meat + vegetable in selected combo.")

    diversity_score = main_div_score + method_div_score + mix_score

    if len(combo) > 1 and unique_main < len(combo):
        repetition_penalty = 8.0 * (len(combo) - unique_main)
        diversity_score -= repetition_penalty
        notes.append("Penalized repeated main ingredients.")

    if len(combo) > 1 and unique_method == 1:
        diversity_score -= 6.0
        notes.append("Penalized low cooking-method diversity.")

    avg_time = sum(r.cook_time_minutes for r in combo) / len(combo)
    wants_simple = "simple" in constraints or "quick" in constraints or "short" in constraints

    if wants_simple:
        cooking_time_score = max(0.0, 20.0 - max(0.0, avg_time - 20.0) * 0.6)
    else:
        cooking_time_score = max(0.0, 20.0 - max(0.0, avg_time - 35.0) * 0.35)

    easy_count = sum(1 for r in combo if (r.difficulty or "").lower() == "easy")
    easy_ratio = easy_count / len(combo)

    preference_matches = sum(1 for r in combo if _matches_preferences(r, preferences))
    pref_ratio = preference_matches / len(combo) if preferences else 1.0

    constraint_score = 0.0
    if wants_simple:
        constraint_score += 6.0 * easy_ratio
        if avg_time <= 30:
            constraint_score += 2.5
    else:
        constraint_score += 3.0

    constraint_score += 1.5 * pref_ratio
    constraint_score = min(10.0, constraint_score)

    total_score = ingredient_score + diversity_score + cooking_time_score + constraint_score

    breakdown = {
        "ingredient_match": round(ingredient_score, 2),
        "diversity": round(diversity_score, 2),
        "cooking_time": round(cooking_time_score, 2),
        "constraint_satisfaction": round(constraint_score, 2),
    }

    return round(total_score, 2), breakdown, notes


def generate_best_menu(db: Session, payload: MenuGenerateRequest) -> MenuGenerateResponse:
    recipes = db.execute(
        select(Recipe).options(
            selectinload(Recipe.recipe_ingredients).selectinload(RecipeIngredient.ingredient)
        )
    ).scalars().all()

    if not recipes:
        raise ValueError("No recipes available. Please create recipes first.")

    preferences = _norm_set(payload.preferences)
    available_ingredients = _norm_set(payload.available_ingredients)
    constraints = _norm_set(payload.constraints)

    candidate_recipes = [r for r in recipes if _matches_preferences(r, preferences)]
    if not candidate_recipes:
        candidate_recipes = recipes

    if len(candidate_recipes) < payload.dish_count:
        raise ValueError(
            f"Not enough candidate recipes ({len(candidate_recipes)}) for dish_count={payload.dish_count}."
        )

    candidate_has_meat = any((r.dish_type or "").lower() == "meat" for r in candidate_recipes)
    candidate_has_veg = any((r.dish_type or "").lower() == "vegetable" for r in candidate_recipes)

    best_combo = None
    best_score = float("-inf")
    best_breakdown = {}
    best_notes: List[str] = []

    for combo in combinations(candidate_recipes, payload.dish_count):
        total, breakdown, notes = _score_combo(
            combo=combo,
            available_ingredients=available_ingredients,
            constraints=constraints,
            preferences=preferences,
            candidate_has_meat=candidate_has_meat,
            candidate_has_veg=candidate_has_veg,
        )
        if total > best_score:
            best_score = total
            best_combo = combo
            best_breakdown = breakdown
            best_notes = notes

    if not best_combo:
        raise ValueError("Unable to generate menu from current recipes.")

    dishes = [
        MenuDish(
            recipe_id=r.id,
            name=r.name,
            cook_time_minutes=r.cook_time_minutes,
            difficulty=r.difficulty,
            dish_type=r.dish_type,
            cooking_method=r.cooking_method,
            main_ingredient=r.main_ingredient,
        )
        for r in best_combo
    ]

    if preferences:
        best_notes.append(f"Preferences considered: {', '.join(sorted(preferences))}")
    if constraints:
        best_notes.append(f"Constraints considered: {', '.join(sorted(constraints))}")

    return MenuGenerateResponse(
        dishes=dishes,
        total_score=best_score,
        score_breakdown=best_breakdown,
        notes=list(dict.fromkeys(best_notes)),
    )
