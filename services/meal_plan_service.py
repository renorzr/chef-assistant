from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import MealPlan, MealPlanItem, Recipe
from schemas import MealPlanItemCreateRequest, MealPlanItemRead, MealPlanRead, MealPlanSummaryRead, MealPlanUpdateRequest


def _default_meal_plan_name(now: datetime | None = None) -> str:
    now = now or datetime.now()
    weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"{now.month}月{now.day}日 {weekday_map[now.weekday()]}"


def _item_to_read(item: MealPlanItem) -> MealPlanItemRead:
    return MealPlanItemRead(
        id=item.id,
        meal_plan_id=item.meal_plan_id,
        recipe_id=item.recipe_id,
        recipe_name=item.recipe.name if item.recipe else "",
        recipe_cover_image_url=item.recipe.cover_image_url if item.recipe else None,
        recipe_cook_time_minutes=item.recipe.cook_time_minutes if item.recipe else None,
        recipe_difficulty=item.recipe.difficulty if item.recipe else None,
        sort_order=item.sort_order,
        notes=item.notes,
    )


def _meal_plan_to_read(meal_plan: MealPlan) -> MealPlanRead:
    items = [_item_to_read(item) for item in sorted(meal_plan.items, key=lambda x: (x.sort_order, x.id))]
    return MealPlanRead(
        id=meal_plan.id,
        name=meal_plan.name,
        status=meal_plan.status,
        completed_at=meal_plan.completed_at.isoformat() if meal_plan.completed_at else None,
        items=items,
    )


def _load_meal_plan(db: Session, meal_plan_id: int) -> MealPlan | None:
    return db.execute(
        select(MealPlan)
        .where(MealPlan.id == meal_plan_id)
        .options(selectinload(MealPlan.items).selectinload(MealPlanItem.recipe))
    ).scalar_one_or_none()


def get_current_meal_plan(db: Session) -> MealPlanRead | None:
    meal_plan = db.execute(
        select(MealPlan)
        .where(MealPlan.status == "editing")
        .options(selectinload(MealPlan.items).selectinload(MealPlanItem.recipe))
        .order_by(MealPlan.id.asc())
    ).scalar_one_or_none()
    if not meal_plan:
        return None
    return _meal_plan_to_read(meal_plan)


def ensure_current_meal_plan(db: Session) -> MealPlanRead:
    current = get_current_meal_plan(db)
    if current:
        return current

    meal_plan = MealPlan(name=_default_meal_plan_name(), status="editing")
    db.add(meal_plan)
    db.commit()
    loaded = _load_meal_plan(db, meal_plan.id)
    return _meal_plan_to_read(loaded)


def get_meal_plan(db: Session, meal_plan_id: int) -> MealPlanRead:
    meal_plan = _load_meal_plan(db, meal_plan_id)
    if not meal_plan:
        raise ValueError("Meal plan not found.")
    return _meal_plan_to_read(meal_plan)


def update_meal_plan(db: Session, meal_plan_id: int, payload: MealPlanUpdateRequest) -> MealPlanRead:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise ValueError("Meal plan not found.")

    meal_plan.name = payload.name.strip()
    db.commit()
    return get_meal_plan(db, meal_plan_id)


def list_recent_meal_plans(db: Session, limit: int = 5) -> list[MealPlanSummaryRead]:
    subq = (
        select(MealPlan.id)
        .order_by(MealPlan.updated_at.desc(), MealPlan.id.desc())
        .limit(max(1, min(limit, 20)))
        .subquery()
    )
    rows = db.execute(
        select(MealPlan.id, MealPlan.name, MealPlan.status, MealPlan.completed_at, MealPlan.updated_at, func.count(MealPlanItem.id))
        .join(subq, subq.c.id == MealPlan.id)
        .outerjoin(MealPlanItem, MealPlanItem.meal_plan_id == MealPlan.id)
        .group_by(MealPlan.id)
        .order_by(MealPlan.updated_at.asc(), MealPlan.id.asc())
    ).all()
    return [
        MealPlanSummaryRead(
            id=row[0],
            name=row[1],
            status=row[2],
            completed_at=row[3].isoformat() if row[3] else None,
            updated_at=row[4].isoformat() if row[4] else None,
            item_count=int(row[5] or 0),
        )
        for row in rows
    ]


def add_recipe_to_current_meal_plan(db: Session, payload: MealPlanItemCreateRequest) -> MealPlanRead:
    current = ensure_current_meal_plan(db)
    meal_plan = _load_meal_plan(db, current.id)

    recipe = db.get(Recipe, payload.recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    exists = db.execute(
        select(MealPlanItem.id).where(MealPlanItem.meal_plan_id == meal_plan.id, MealPlanItem.recipe_id == payload.recipe_id)
    ).scalar_one_or_none()
    if exists:
        return _meal_plan_to_read(meal_plan)

    next_sort = len(meal_plan.items)
    db.add(MealPlanItem(meal_plan_id=meal_plan.id, recipe_id=payload.recipe_id, sort_order=next_sort))
    db.commit()
    loaded = _load_meal_plan(db, meal_plan.id)
    return _meal_plan_to_read(loaded)


def remove_meal_plan_item(db: Session, meal_plan_id: int, item_id: int) -> bool:
    item = db.get(MealPlanItem, item_id)
    if not item or item.meal_plan_id != meal_plan_id:
        return False
    db.delete(item)
    db.commit()
    return True


def complete_meal_plan(db: Session, meal_plan_id: int) -> MealPlanRead:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise ValueError("Meal plan not found.")
    meal_plan.status = "completed"
    meal_plan.completed_at = datetime.now()
    db.commit()
    return get_meal_plan(db, meal_plan_id)


def resume_meal_plan(db: Session, meal_plan_id: int) -> MealPlanRead:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise ValueError("Meal plan not found.")
    if meal_plan.status == "editing":
        return get_meal_plan(db, meal_plan_id)

    current = db.execute(select(MealPlan.id).where(MealPlan.status == "editing")).scalar_one_or_none()
    if current is not None:
        raise ValueError("Another meal plan is currently being edited.")

    meal_plan.status = "editing"
    meal_plan.completed_at = None
    db.commit()
    return get_meal_plan(db, meal_plan_id)


def delete_meal_plan(db: Session, meal_plan_id: int) -> bool:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        return False
    db.delete(meal_plan)
    db.commit()
    return True
