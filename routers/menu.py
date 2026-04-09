from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import MenuGenerateRequest, MenuGenerateResponse
from services.menu_service import generate_best_menu

router = APIRouter()


@router.post("/menu/generate", response_model=MenuGenerateResponse)
def generate_menu_endpoint(payload: MenuGenerateRequest, db: Session = Depends(get_db)):
    try:
        return generate_best_menu(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
