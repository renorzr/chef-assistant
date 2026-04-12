import re
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from models import Menu, MenuCategory, MenuItem, Recipe
from schemas import (
    MenuCreateRequest,
    MenuUpdateRequest,
    MenuSummaryRead,
    MenuCategoryCreateRequest,
    MenuCategoryUpdateRequest,
    MenuCategoryRead,
    MenuItemCreateRequest,
    MenuItemUpdateRequest,
    MenuItemRead,
    MenuRead,
    MenuGenerateFromTextRequest,
    MenuGenerateFromTextResponse,
    MenuGenerateRequest,
)
from services.menu_service import generate_best_menu


def _menu_to_read(menu: Menu) -> MenuRead:
    categories = [
        MenuCategoryRead(
            id=c.id,
            menu_id=c.menu_id,
            name=c.name,
            sort_order=c.sort_order,
        )
        for c in sorted(menu.categories, key=lambda x: (x.sort_order, x.id))
    ]

    items = [
        MenuItemRead(
            id=i.id,
            menu_id=i.menu_id,
            recipe_id=i.recipe_id,
            recipe_name=i.recipe.name if i.recipe else "",
            recipe_cover_image_url=i.recipe.cover_image_url if i.recipe else None,
            recipe_cook_time_minutes=i.recipe.cook_time_minutes if i.recipe else None,
            recipe_difficulty=i.recipe.difficulty if i.recipe else None,
            category_id=i.category_id,
            category_name=i.category.name if i.category else None,
            item_name_override=i.item_name_override,
            notes=i.notes,
            sort_order=i.sort_order,
        )
        for i in sorted(menu.items, key=lambda x: (x.sort_order, x.id))
    ]

    return MenuRead(
        id=menu.id,
        name=menu.name,
        description=menu.description,
        preference_text=menu.preference_text,
        categories=categories,
        items=items,
    )


def _load_menu(db: Session, menu_id: int) -> Menu | None:
    return db.execute(
        select(Menu)
        .where(Menu.id == menu_id)
        .options(
            selectinload(Menu.categories),
            selectinload(Menu.items).selectinload(MenuItem.recipe),
            selectinload(Menu.items).selectinload(MenuItem.category),
        )
    ).scalar_one_or_none()


def create_menu(db: Session, payload: MenuCreateRequest) -> MenuRead:
    menu = Menu(
        name=payload.name.strip(),
        description=payload.description,
        preference_text=payload.preference_text,
    )
    db.add(menu)
    db.commit()
    db.refresh(menu)
    loaded = _load_menu(db, menu.id)
    return _menu_to_read(loaded)


def list_menus(db: Session) -> List[MenuSummaryRead]:
    rows = db.execute(
        select(Menu.id, Menu.name, Menu.description, Menu.preference_text, func.count(MenuItem.id))
        .outerjoin(MenuItem, MenuItem.menu_id == Menu.id)
        .group_by(Menu.id)
        .order_by(Menu.id.asc())
    ).all()

    return [
        MenuSummaryRead(
            id=row[0],
            name=row[1],
            description=row[2],
            preference_text=row[3],
            item_count=int(row[4] or 0),
        )
        for row in rows
    ]


def get_menu(db: Session, menu_id: int) -> MenuRead:
    menu = _load_menu(db, menu_id)
    if not menu:
        raise ValueError("Menu not found.")
    return _menu_to_read(menu)


def update_menu(db: Session, menu_id: int, payload: MenuUpdateRequest) -> MenuRead:
    menu = db.get(Menu, menu_id)
    if not menu:
        raise ValueError("Menu not found.")

    menu.name = payload.name.strip()
    menu.description = payload.description
    menu.preference_text = payload.preference_text
    db.commit()
    return get_menu(db, menu_id)


def delete_menu(db: Session, menu_id: int) -> bool:
    menu = db.get(Menu, menu_id)
    if not menu:
        return False
    db.delete(menu)
    db.commit()
    return True


def create_menu_category(db: Session, menu_id: int, payload: MenuCategoryCreateRequest) -> MenuCategoryRead:
    menu = db.get(Menu, menu_id)
    if not menu:
        raise ValueError("Menu not found.")

    exists = db.execute(
        select(MenuCategory.id).where(
            MenuCategory.menu_id == menu_id,
            MenuCategory.name == payload.name.strip(),
        )
    ).scalar_one_or_none()
    if exists:
        raise ValueError("Category name already exists in this menu.")

    category = MenuCategory(
        menu_id=menu_id,
        name=payload.name.strip(),
        sort_order=payload.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return MenuCategoryRead(
        id=category.id,
        menu_id=category.menu_id,
        name=category.name,
        sort_order=category.sort_order,
    )


def list_menu_categories(db: Session, menu_id: int) -> List[MenuCategoryRead]:
    rows = db.execute(
        select(MenuCategory)
        .where(MenuCategory.menu_id == menu_id)
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.id.asc())
    ).scalars().all()
    return [
        MenuCategoryRead(id=r.id, menu_id=r.menu_id, name=r.name, sort_order=r.sort_order)
        for r in rows
    ]


def update_menu_category(
    db: Session,
    menu_id: int,
    category_id: int,
    payload: MenuCategoryUpdateRequest,
) -> MenuCategoryRead:
    category = db.get(MenuCategory, category_id)
    if not category or category.menu_id != menu_id:
        raise ValueError("Category not found.")

    dup = db.execute(
        select(MenuCategory.id).where(
            MenuCategory.menu_id == menu_id,
            MenuCategory.name == payload.name.strip(),
            MenuCategory.id != category_id,
        )
    ).scalar_one_or_none()
    if dup:
        raise ValueError("Category name already exists in this menu.")

    category.name = payload.name.strip()
    category.sort_order = payload.sort_order
    db.commit()
    db.refresh(category)
    return MenuCategoryRead(
        id=category.id,
        menu_id=category.menu_id,
        name=category.name,
        sort_order=category.sort_order,
    )


def delete_menu_category(db: Session, menu_id: int, category_id: int) -> bool:
    category = db.get(MenuCategory, category_id)
    if not category or category.menu_id != menu_id:
        return False

    for item in category.items:
        item.category_id = None
    db.delete(category)
    db.commit()
    return True


def create_menu_item(db: Session, menu_id: int, payload: MenuItemCreateRequest) -> MenuItemRead:
    menu = db.get(Menu, menu_id)
    if not menu:
        raise ValueError("Menu not found.")

    recipe = db.get(Recipe, payload.recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    category = None
    if payload.category_id is not None:
        category = db.get(MenuCategory, payload.category_id)
        if not category or category.menu_id != menu_id:
            raise ValueError("Category not found in this menu.")

    item = MenuItem(
        menu_id=menu_id,
        recipe_id=payload.recipe_id,
        category_id=payload.category_id,
        item_name_override=payload.item_name_override,
        notes=payload.notes,
        sort_order=payload.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return MenuItemRead(
        id=item.id,
        menu_id=item.menu_id,
        recipe_id=item.recipe_id,
        recipe_name=recipe.name,
        recipe_cover_image_url=recipe.cover_image_url,
        recipe_cook_time_minutes=recipe.cook_time_minutes,
        recipe_difficulty=recipe.difficulty,
        category_id=item.category_id,
        category_name=category.name if category else None,
        item_name_override=item.item_name_override,
        notes=item.notes,
        sort_order=item.sort_order,
    )


def list_menu_items(db: Session, menu_id: int) -> List[MenuItemRead]:
    rows = db.execute(
        select(MenuItem)
        .where(MenuItem.menu_id == menu_id)
        .options(selectinload(MenuItem.recipe), selectinload(MenuItem.category))
        .order_by(MenuItem.sort_order.asc(), MenuItem.id.asc())
    ).scalars().all()

    return [
        MenuItemRead(
            id=r.id,
            menu_id=r.menu_id,
            recipe_id=r.recipe_id,
            recipe_name=r.recipe.name if r.recipe else "",
            recipe_cover_image_url=r.recipe.cover_image_url if r.recipe else None,
            recipe_cook_time_minutes=r.recipe.cook_time_minutes if r.recipe else None,
            recipe_difficulty=r.recipe.difficulty if r.recipe else None,
            category_id=r.category_id,
            category_name=r.category.name if r.category else None,
            item_name_override=r.item_name_override,
            notes=r.notes,
            sort_order=r.sort_order,
        )
        for r in rows
    ]


def update_menu_item(
    db: Session,
    menu_id: int,
    item_id: int,
    payload: MenuItemUpdateRequest,
) -> MenuItemRead:
    item = db.get(MenuItem, item_id)
    if not item or item.menu_id != menu_id:
        raise ValueError("Menu item not found.")

    recipe = db.get(Recipe, payload.recipe_id)
    if not recipe:
        raise ValueError("Recipe not found.")

    category = None
    if payload.category_id is not None:
        category = db.get(MenuCategory, payload.category_id)
        if not category or category.menu_id != menu_id:
            raise ValueError("Category not found in this menu.")

    item.recipe_id = payload.recipe_id
    item.category_id = payload.category_id
    item.item_name_override = payload.item_name_override
    item.notes = payload.notes
    item.sort_order = payload.sort_order
    db.commit()
    db.refresh(item)

    return MenuItemRead(
        id=item.id,
        menu_id=item.menu_id,
        recipe_id=item.recipe_id,
        recipe_name=recipe.name,
        recipe_cover_image_url=recipe.cover_image_url,
        recipe_cook_time_minutes=recipe.cook_time_minutes,
        recipe_difficulty=recipe.difficulty,
        category_id=item.category_id,
        category_name=category.name if category else None,
        item_name_override=item.item_name_override,
        notes=item.notes,
        sort_order=item.sort_order,
    )


def delete_menu_item(db: Session, menu_id: int, item_id: int) -> bool:
    item = db.get(MenuItem, item_id)
    if not item or item.menu_id != menu_id:
        return False
    db.delete(item)
    db.commit()
    return True


def _extract_keywords(text: str, candidates: list[str]) -> list[str]:
    lower = text.lower()
    return [c for c in candidates if c in lower]


def _parse_menu_text(text: str, override_dish_count: int | None) -> dict:
    lower = text.lower()
    dish_count = override_dish_count
    if dish_count is None:
        m = re.search(r"(\d+)\s*(道|个|dish)", lower)
        if m:
            dish_count = max(1, min(int(m.group(1)), 20))
    if dish_count is None:
        dish_count = 4

    preferences = _extract_keywords(
        lower,
        ["fish", "chicken", "beef", "pork", "seafood", "vegetable", "清淡", "辣", "川菜", "粤菜", "家常"],
    )
    constraints = _extract_keywords(lower, ["simple", "quick", "short", "easy", "简单", "快手", "低脂", "清淡"])
    available = _extract_keywords(
        lower,
        ["egg", "tomato", "potato", "garlic", "onion", "鸡蛋", "番茄", "土豆", "蒜", "洋葱"],
    )

    categories = []
    if any(k in lower for k in ["冷菜", "炒菜", "汤"]):
        categories = [c for c in ["冷菜", "炒菜", "汤"] if c in lower]
    elif any(k in lower for k in ["前菜", "主食", "甜点", "主菜"]):
        categories = [c for c in ["前菜", "主菜", "主食", "甜点"] if c in lower]

    return {
        "dish_count": dish_count,
        "preferences": preferences,
        "constraints": constraints,
        "available_ingredients": available,
        "categories": categories,
    }


def _assign_category_name(recipe_name: str, method: str, categories: list[str], index: int) -> str | None:
    if not categories:
        return None
    if "汤" in categories and method == "soup":
        return "汤"
    if "炒菜" in categories and method in {"fry", "sear"}:
        return "炒菜"
    if "冷菜" in categories and any(k in recipe_name.lower() for k in ["salad", "cold", "凉", "拌"]):
        return "冷菜"

    if "甜点" in categories and any(k in recipe_name.lower() for k in ["dessert", "sweet", "cake", "布丁", "甜"]):
        return "甜点"
    if "前菜" in categories and index == 0:
        return "前菜"
    if "主菜" in categories:
        return "主菜"
    if "主食" in categories:
        return "主食"

    return categories[min(index, len(categories) - 1)]


def generate_menu_from_text(db: Session, payload: MenuGenerateFromTextRequest) -> MenuGenerateFromTextResponse:
    parsed = _parse_menu_text(payload.preference_text, payload.dish_count)

    generated = generate_best_menu(
        db,
        MenuGenerateRequest(
            people_count=1,
            dish_count=parsed["dish_count"],
            preferences=parsed["preferences"],
            available_ingredients=parsed["available_ingredients"],
            constraints=parsed["constraints"],
        ),
    )

    menu = Menu(
        name=payload.name.strip(),
        description=None,
        preference_text=payload.preference_text,
    )
    db.add(menu)
    db.flush()

    category_map = {}
    for idx, name in enumerate(parsed["categories"]):
        c = MenuCategory(menu_id=menu.id, name=name, sort_order=idx)
        db.add(c)
        db.flush()
        category_map[name] = c.id

    for idx, dish in enumerate(generated.dishes):
        category_name = _assign_category_name(dish.name, dish.cooking_method, parsed["categories"], idx)
        category_id = category_map.get(category_name) if category_name else None
        db.add(
            MenuItem(
                menu_id=menu.id,
                recipe_id=dish.recipe_id,
                category_id=category_id,
                sort_order=idx,
            )
        )

    db.commit()

    loaded = _load_menu(db, menu.id)
    notes = [
        f"Parsed preference keywords: {', '.join(parsed['preferences']) or 'none'}",
        f"Parsed constraints: {', '.join(parsed['constraints']) or 'none'}",
        f"Parsed category hints: {', '.join(parsed['categories']) or 'none'}",
    ]

    return MenuGenerateFromTextResponse(
        menu=_menu_to_read(loaded),
        generation_notes=notes + generated.notes,
        score_breakdown=generated.score_breakdown,
    )
