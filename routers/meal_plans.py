from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import MealPlanAddItemResponse, MealPlanItemCreateRequest, MealPlanRead, MealPlanSummaryRead, MealPlanUpdateRequest
from services.meal_plan_service import (
    add_recipe_to_current_meal_plan,
    complete_meal_plan,
    copy_meal_plan,
    cancel_meal_plan,
    delete_meal_plan,
    ensure_current_meal_plan,
    get_current_meal_plan,
    get_meal_plan,
    list_recent_meal_plans,
    remove_meal_plan_item,
    resume_meal_plan,
    update_meal_plan,
)

router = APIRouter()


@router.get("/meal-plans/current", response_model=MealPlanRead | None)
def get_current_meal_plan_endpoint(db: Session = Depends(get_db)):
    return get_current_meal_plan(db)


@router.post("/meal-plans/current/ensure", response_model=MealPlanRead)
def ensure_current_meal_plan_endpoint(db: Session = Depends(get_db)):
    return ensure_current_meal_plan(db)


@router.post("/meal-plans/current/items", response_model=MealPlanAddItemResponse)
def add_recipe_to_current_meal_plan_endpoint(payload: MealPlanItemCreateRequest, db: Session = Depends(get_db)):
    try:
        return add_recipe_to_current_meal_plan(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/meal-plans", response_model=List[MealPlanSummaryRead])
def list_recent_meal_plans_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    return list_recent_meal_plans(db, limit=limit)


@router.get("/meal-plans/{meal_plan_id}", response_model=MealPlanRead)
def get_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    try:
        return get_meal_plan(db, meal_plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/meal-plans/{meal_plan_id}", response_model=MealPlanRead)
def update_meal_plan_endpoint(meal_plan_id: int, payload: MealPlanUpdateRequest, db: Session = Depends(get_db)):
    try:
        return update_meal_plan(db, meal_plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/meal-plans/{meal_plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    deleted = delete_meal_plan(db, meal_plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meal plan not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/meal-plans/{meal_plan_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_meal_plan_item_endpoint(meal_plan_id: int, item_id: int, db: Session = Depends(get_db)):
    deleted = remove_meal_plan_item(db, meal_plan_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meal plan item not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/meal-plans/{meal_plan_id}/complete", response_model=MealPlanRead)
def complete_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    try:
        return complete_meal_plan(db, meal_plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/meal-plans/{meal_plan_id}/cancel", response_model=MealPlanRead)
def cancel_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    try:
        return cancel_meal_plan(db, meal_plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/meal-plans/{meal_plan_id}/resume", response_model=MealPlanRead)
def resume_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    try:
        return resume_meal_plan(db, meal_plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/meal-plans/{meal_plan_id}/copy", response_model=MealPlanRead)
def copy_meal_plan_endpoint(meal_plan_id: int, db: Session = Depends(get_db)):
    try:
        return copy_meal_plan(db, meal_plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
