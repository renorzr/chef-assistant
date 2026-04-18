from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    RecipeImportFromHtmlRequest,
    RecipeImportFromHtmlResponse,
    RecipeImportFromTextRequest,
    RecipeImportFromTextResponse,
)
from services.import_service import import_recipe_from_text, import_recipes_from_html
from services.vector_tasks import create_recipe_embedding_task

router = APIRouter()


@router.post("/recipes/import/from-html", response_model=RecipeImportFromHtmlResponse, status_code=201)
def import_recipes_from_html_endpoint(payload: RecipeImportFromHtmlRequest, db: Session = Depends(get_db)):
    try:
        return import_recipes_from_html(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/recipes/import/from-text", response_model=RecipeImportFromTextResponse, status_code=201)
def import_recipe_from_text_endpoint(
    payload: RecipeImportFromTextRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        result = import_recipe_from_text(db, payload)
        background_tasks.add_task(create_recipe_embedding_task, result.recipe.id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
