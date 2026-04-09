from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    RecipeCreate,
    RecipeRead,
    VectorSearchRequest,
    VectorSearchResponse,
    HybridSearchRequest,
    HybridSearchResponse,
)
from services.recipe_service import (
    create_recipe,
    list_recipes,
    update_recipe,
    delete_recipe,
    get_recipe_by_id,
    search_recipes_by_vector,
    search_recipes_hybrid,
)
from services.vector_tasks import create_recipe_embedding_task

router = APIRouter()


@router.post("/recipes", response_model=RecipeRead, status_code=201)
def create_recipe_endpoint(
    payload: RecipeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    recipe = create_recipe(db, payload)
    background_tasks.add_task(create_recipe_embedding_task, recipe.id)
    return recipe


@router.get("/recipes", response_model=List[RecipeRead])
def list_recipes_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return list_recipes(db, skip=skip, limit=limit)


@router.post("/recipes/search/vector", response_model=VectorSearchResponse)
def vector_search_recipes_endpoint(payload: VectorSearchRequest, db: Session = Depends(get_db)):
    try:
        return search_recipes_by_vector(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/recipes/search/hybrid", response_model=HybridSearchResponse)
def hybrid_search_recipes_endpoint(payload: HybridSearchRequest, db: Session = Depends(get_db)):
    try:
        return search_recipes_hybrid(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    recipe = get_recipe_by_id(db, recipe_id=recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe


@router.put("/recipes/{recipe_id}", response_model=RecipeRead)
def update_recipe_endpoint(
    recipe_id: int,
    payload: RecipeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        recipe = update_recipe(db, recipe_id=recipe_id, payload=payload)
        background_tasks.add_task(create_recipe_embedding_task, recipe.id)
        return recipe
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe_endpoint(recipe_id: int, db: Session = Depends(get_db)):
    deleted = delete_recipe(db, recipe_id=recipe_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
