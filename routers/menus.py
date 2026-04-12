from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    MenuCreateRequest,
    MenuUpdateRequest,
    MenuSummaryRead,
    MenuRead,
    MenuCategoryCreateRequest,
    MenuCategoryUpdateRequest,
    MenuCategoryRead,
    MenuItemCreateRequest,
    MenuItemUpdateRequest,
    MenuItemRead,
    MenuGenerateFromTextRequest,
    MenuGenerateFromTextResponse,
)
from services.menu_template_service import (
    create_menu,
    list_menus,
    get_menu,
    update_menu,
    delete_menu,
    create_menu_category,
    list_menu_categories,
    update_menu_category,
    delete_menu_category,
    create_menu_item,
    list_menu_items,
    update_menu_item,
    delete_menu_item,
    generate_menu_from_text,
)

router = APIRouter()


@router.post("/menus", response_model=MenuRead, status_code=201)
def create_menu_endpoint(payload: MenuCreateRequest, db: Session = Depends(get_db)):
    return create_menu(db, payload)


@router.get("/menus", response_model=List[MenuSummaryRead])
def list_menus_endpoint(db: Session = Depends(get_db)):
    return list_menus(db)


@router.post("/menus/generate-from-text", response_model=MenuGenerateFromTextResponse, status_code=201)
def generate_menu_from_text_endpoint(payload: MenuGenerateFromTextRequest, db: Session = Depends(get_db)):
    try:
        return generate_menu_from_text(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/menus/{menu_id}", response_model=MenuRead)
def get_menu_endpoint(menu_id: int, db: Session = Depends(get_db)):
    try:
        return get_menu(db, menu_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/menus/{menu_id}", response_model=MenuRead)
def update_menu_endpoint(menu_id: int, payload: MenuUpdateRequest, db: Session = Depends(get_db)):
    try:
        return update_menu(db, menu_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_endpoint(menu_id: int, db: Session = Depends(get_db)):
    deleted = delete_menu(db, menu_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Menu not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/menus/{menu_id}/categories", response_model=MenuCategoryRead, status_code=201)
def create_menu_category_endpoint(
    menu_id: int,
    payload: MenuCategoryCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return create_menu_category(db, menu_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/menus/{menu_id}/categories", response_model=List[MenuCategoryRead])
def list_menu_categories_endpoint(menu_id: int, db: Session = Depends(get_db)):
    return list_menu_categories(db, menu_id)


@router.put("/menus/{menu_id}/categories/{category_id}", response_model=MenuCategoryRead)
def update_menu_category_endpoint(
    menu_id: int,
    category_id: int,
    payload: MenuCategoryUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return update_menu_category(db, menu_id, category_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/menus/{menu_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_category_endpoint(menu_id: int, category_id: int, db: Session = Depends(get_db)):
    deleted = delete_menu_category(db, menu_id, category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/menus/{menu_id}/items", response_model=MenuItemRead, status_code=201)
def create_menu_item_endpoint(menu_id: int, payload: MenuItemCreateRequest, db: Session = Depends(get_db)):
    try:
        return create_menu_item(db, menu_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/menus/{menu_id}/items", response_model=List[MenuItemRead])
def list_menu_items_endpoint(menu_id: int, db: Session = Depends(get_db)):
    return list_menu_items(db, menu_id)


@router.put("/menus/{menu_id}/items/{item_id}", response_model=MenuItemRead)
def update_menu_item_endpoint(
    menu_id: int,
    item_id: int,
    payload: MenuItemUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        return update_menu_item(db, menu_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/menus/{menu_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item_endpoint(menu_id: int, item_id: int, db: Session = Depends(get_db)):
    deleted = delete_menu_item(db, menu_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Menu item not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
