from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import MealPlan, MealPlanItem, Recipe
from schemas import (
    MealPlanAddItemResponse,
    MealPlanItemCreateRequest,
    MealPlanItemRead,
    MealPlanRead,
    MealPlanSummaryRead,
    MealPlanUpdateRequest,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _default_meal_plan_name(now: datetime | None = None) -> str:
    current = now.astimezone() if now else datetime.now().astimezone()
    weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return f"{current.month}月{current.day}日 {weekday_map[current.weekday()]}"


def _default_expected_finish_at(now: datetime | None = None) -> datetime:
    current = now or _now()
    return current + timedelta(hours=24)


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
        expected_finish_at=meal_plan.expected_finish_at.isoformat() if meal_plan.expected_finish_at else None,
        completed_at=meal_plan.completed_at.isoformat() if meal_plan.completed_at else None,
        cancelled_at=meal_plan.cancelled_at.isoformat() if meal_plan.cancelled_at else None,
        items=items,
    )


def _load_meal_plan(db: Session, meal_plan_id: int) -> MealPlan | None:
    return db.execute(
        select(MealPlan)
        .where(MealPlan.id == meal_plan_id)
        .options(selectinload(MealPlan.items).selectinload(MealPlanItem.recipe))
    ).scalar_one_or_none()


def _get_current_meal_plan_model(db: Session) -> MealPlan | None:
    return db.execute(
        select(MealPlan)
        .where(MealPlan.status == "editing")
        .options(selectinload(MealPlan.items).selectinload(MealPlanItem.recipe))
        .order_by(MealPlan.id.asc())
    ).scalar_one_or_none()


def _create_meal_plan_model(db: Session, name: str | None = None) -> MealPlan:
    now = _now()
    meal_plan = MealPlan(
        name=name or _default_meal_plan_name(now),
        status="editing",
        expected_finish_at=_default_expected_finish_at(now),
    )
    db.add(meal_plan)
    db.flush()
    return meal_plan


def _is_expired(meal_plan: MealPlan) -> bool:
    if meal_plan.status != "editing":
        return False
    expected = _as_utc(meal_plan.expected_finish_at)
    return bool(expected and expected < _now())


def get_current_meal_plan(db: Session) -> MealPlanRead | None:
    meal_plan = _get_current_meal_plan_model(db)
    if not meal_plan:
        return None
    return _meal_plan_to_read(meal_plan)


def ensure_current_meal_plan(db: Session) -> MealPlanRead:
    meal_plan = _get_current_meal_plan_model(db)
    if not meal_plan:
        meal_plan = _create_meal_plan_model(db)
        db.commit()
        meal_plan = _load_meal_plan(db, meal_plan.id)
    return _meal_plan_to_read(meal_plan)


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
        select(
            MealPlan.id,
            MealPlan.name,
            MealPlan.status,
            MealPlan.expected_finish_at,
            MealPlan.completed_at,
            MealPlan.cancelled_at,
            MealPlan.updated_at,
            func.count(MealPlanItem.id),
        )
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
            expected_finish_at=row[3].isoformat() if row[3] else None,
            completed_at=row[4].isoformat() if row[4] else None,
            cancelled_at=row[5].isoformat() if row[5] else None,
            updated_at=row[6].isoformat() if row[6] else None,
            item_count=int(row[7] or 0),
        )
        for row in rows
    ]


def _add_recipe_to_plan(db: Session, meal_plan: MealPlan, recipe_id: int) -> MealPlan:
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    exists = db.execute(
        select(MealPlanItem.id).where(MealPlanItem.meal_plan_id == meal_plan.id, MealPlanItem.recipe_id == recipe_id)
    ).scalar_one_or_none()
    if exists:
        return meal_plan

    db.add(MealPlanItem(meal_plan_id=meal_plan.id, recipe_id=recipe_id, sort_order=len(meal_plan.items)))
    db.flush()
    return _load_meal_plan(db, meal_plan.id)


def add_recipe_to_current_meal_plan(db: Session, payload: MealPlanItemCreateRequest) -> MealPlanAddItemResponse:
    on_expired = (payload.on_expired or "ask").strip().lower()
    if on_expired not in {"ask", "continue", "complete", "cancel"}:
        raise ValueError("Invalid on_expired action.")

    meal_plan = _get_current_meal_plan_model(db)
    if not meal_plan:
        meal_plan = _create_meal_plan_model(db)

    if _is_expired(meal_plan):
        if on_expired == "ask":
            return MealPlanAddItemResponse(
                status="expired_confirmation_required",
                message="当前编辑中的餐单已超过预计完成时间，请选择如何处理。",
                meal_plan=_meal_plan_to_read(meal_plan),
            )
        if on_expired == "continue":
            meal_plan.expected_finish_at = _default_expected_finish_at()
        elif on_expired == "complete":
            meal_plan.status = "completed"
            meal_plan.completed_at = _now()
            meal_plan = _create_meal_plan_model(db)
        elif on_expired == "cancel":
            meal_plan.status = "cancelled"
            meal_plan.cancelled_at = _now()
            meal_plan = _create_meal_plan_model(db)

    meal_plan = _add_recipe_to_plan(db, meal_plan, payload.recipe_id)
    db.commit()
    meal_plan = _load_meal_plan(db, meal_plan.id)
    return MealPlanAddItemResponse(
        status="added",
        message="已加入餐单。",
        meal_plan=_meal_plan_to_read(meal_plan),
    )


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
    meal_plan.completed_at = _now()
    db.commit()
    return get_meal_plan(db, meal_plan_id)


def cancel_meal_plan(db: Session, meal_plan_id: int) -> MealPlanRead:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        raise ValueError("Meal plan not found.")
    meal_plan.status = "cancelled"
    meal_plan.cancelled_at = _now()
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

    if meal_plan.status not in {"completed", "cancelled"}:
        raise ValueError("This meal plan cannot be resumed.")

    meal_plan.status = "editing"
    meal_plan.completed_at = None
    meal_plan.cancelled_at = None
    meal_plan.expected_finish_at = _default_expected_finish_at()
    db.commit()
    return get_meal_plan(db, meal_plan_id)


def copy_meal_plan(db: Session, meal_plan_id: int) -> MealPlanRead:
    source = _load_meal_plan(db, meal_plan_id)
    if not source:
        raise ValueError("Meal plan not found.")
    if source.status not in {"completed", "cancelled"}:
        raise ValueError("Only completed or cancelled meal plans can be copied.")
    current = db.execute(select(MealPlan.id).where(MealPlan.status == "editing")).scalar_one_or_none()
    if current is not None:
        raise ValueError("Another meal plan is currently being edited.")

    copied = _create_meal_plan_model(db, name=f"{source.name}（复制）")
    for idx, item in enumerate(sorted(source.items, key=lambda x: (x.sort_order, x.id))):
        db.add(MealPlanItem(meal_plan_id=copied.id, recipe_id=item.recipe_id, sort_order=idx, notes=item.notes))
    db.commit()
    return get_meal_plan(db, copied.id)


def delete_meal_plan(db: Session, meal_plan_id: int) -> bool:
    meal_plan = db.get(MealPlan, meal_plan_id)
    if not meal_plan:
        return False
    db.delete(meal_plan)
    db.commit()
    return True
