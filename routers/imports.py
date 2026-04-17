from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import RecipeImportFromHtmlRequest, RecipeImportFromHtmlResponse
from services.import_service import import_recipes_from_html

router = APIRouter()


@router.post("/recipes/import/from-html", response_model=RecipeImportFromHtmlResponse, status_code=201)
def import_recipes_from_html_endpoint(payload: RecipeImportFromHtmlRequest, db: Session = Depends(get_db)):
    try:
        return import_recipes_from_html(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
