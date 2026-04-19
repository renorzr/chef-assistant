import json
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Recipe
from schemas import (
    RecipeCreate,
    RecipeImportFromHtmlRequest,
    RecipeImportFromHtmlResponse,
    RecipeImportFromHtmlResult,
    RecipeImportFromTextRequest,
    RecipeImportFromTextResponse,
)
from services.ingredient_service import parse_ingredient_lines_with_llm
from services.recipe_parser_llm import parse_recipe_text_with_llm, parse_recipe_with_llm, RecipeParserError
from services.recipe_service import create_recipe


SUPPORTED_DOMAIN = "xiachufang.com"


def _is_supported_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower()
    return host == SUPPORTED_DOMAIN or host.endswith(f".{SUPPORTED_DOMAIN}")


def _normalize_recipe_url(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?xiachufang\.com/recipe/(\d+)/?", url, flags=re.IGNORECASE)
    if m:
        return f"https://www.xiachufang.com/recipe/{m.group(1)}/"
    return url.strip()


def _strip_tags(html_text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_ld_objects(html_text: str) -> list[dict[str, Any]]:
    scripts = re.findall(
        r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    objs: list[dict[str, Any]] = []
    for raw in scripts:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for obj in candidates:
            if isinstance(obj, dict):
                objs.append(obj)
                graph = obj.get("@graph")
                if isinstance(graph, list):
                    objs.extend([x for x in graph if isinstance(x, dict)])
    return objs


def _pick_recipe_ld(objs: list[dict[str, Any]]) -> dict[str, Any] | None:
    for obj in objs:
        t = obj.get("@type")
        if isinstance(t, list):
            if "recipe" in {str(x).lower() for x in t}:
                return obj
        elif isinstance(t, str) and t.lower() == "recipe":
            return obj
    return None


def _extract_meta_content(html_text: str, key: str) -> str | None:
    pattern = rf"<meta[^>]+(?:property|name)=['\"]{re.escape(key)}['\"][^>]+content=['\"](.*?)['\"][^>]*>"
    m = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return unescape(m.group(1)).strip()


def _extract_title(html_text: str) -> str | None:
    m = re.search(r"<title>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _strip_tags(m.group(1)).strip()


def _parse_cook_time_minutes(v: Any) -> int:
    if isinstance(v, int):
        return max(1, v)
    if isinstance(v, str):
        s = v.strip().upper()
        if s.startswith("PT"):
            h = re.search(r"(\d+)H", s)
            m = re.search(r"(\d+)M", s)
            total = (int(h.group(1)) if h else 0) * 60 + (int(m.group(1)) if m else 0)
            return max(1, total)
        minute_match = re.search(r"(\d+)\s*(MIN|M|分钟)", s, flags=re.IGNORECASE)
        if minute_match:
            return max(1, int(minute_match.group(1)))
    return 30


def _infer_cooking_method(name: str, steps: list[str]) -> str:
    text = f"{name} {' '.join(steps)}".lower()
    if any(k in text for k in ["steam", "蒸"]):
        return "steam"
    if any(k in text for k in ["soup", "stew", "汤", "煮"]):
        return "soup"
    if any(k in text for k in ["fry", "stir", "炒", "煎"]):
        return "fry"
    if any(k in text for k in ["bake", "roast", "烤"]):
        return "bake"
    return "other"


def _infer_dish_type(main_ingredient: str) -> str:
    token = main_ingredient.lower()
    meat_markers = ["beef", "chicken", "pork", "lamb", "fish", "salmon", "shrimp", "牛", "鸡", "猪", "羊", "鱼", "虾"]
    veg_markers = ["tofu", "eggplant", "broccoli", "tomato", "cabbage", "豆腐", "茄", "西兰花", "番茄", "白菜", "青菜"]
    if any(m in token for m in meat_markers):
        return "meat"
    if any(m in token for m in veg_markers):
        return "vegetable"
    return "other"


def _guess_difficulty(name: str, steps: list[str]) -> str:
    text = f"{name} {' '.join(steps)}".lower()
    if any(k in text for k in ["easy", "simple", "quick", "简单", "快手"]):
        return "easy"
    if any(k in text for k in ["hard", "复杂", "高级"]):
        return "hard"
    return "medium"


def _image_url_from_any(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, dict):
        url = value.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    if isinstance(value, list):
        for item in value:
            url = _image_url_from_any(item)
            if url:
                return url
    return None


def _extract_step_image_candidates(html_text: str) -> list[str]:
    img_tags = re.findall(r"<img[^>]+>", html_text, flags=re.IGNORECASE)
    scored: list[tuple[int, str]] = []
    for tag in img_tags:
        m = re.search(r"(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]", tag, flags=re.IGNORECASE)
        if not m:
            continue
        url = m.group(1).strip()
        lower = (tag + " " + url).lower()
        if any(k in lower for k in ["icon", "logo", "sprite", "qrcode", "avatar", "ie-story"]):
            continue
        score = 0
        if any(k in lower for k in ["step", "zuofa", "method", "process", "步骤"]):
            score += 3
        if any(k in lower for k in ["avatar", "logo", "icon", "qrcode", "ads", "banner"]):
            score -= 5
        scored.append((score, url))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for _, url in scored:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= 80:
            break
    return out


def _tokenize_for_match(text: str) -> set[str]:
    if not text:
        return set()
    lower = text.lower()
    return set(re.findall(r"[a-z0-9]+", lower) + re.findall(r"[\u4e00-\u9fff]", lower))


def _extract_step_blocks_with_images(html_text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    pattern = re.compile(r"<(li|div|section)[^>]*(?:step|zuofa|method|process|步骤|做法)[^>]*>(.*?)</\1>", flags=re.IGNORECASE | re.DOTALL)
    for _, inner in pattern.findall(html_text):
        img_match = re.search(r"<img[^>]+(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]", inner, flags=re.IGNORECASE)
        if not img_match:
            continue
        image_url = img_match.group(1).strip()
        lower = image_url.lower()
        if any(k in lower for k in ["icon", "logo", "sprite", "qrcode", "avatar", "ie-story"]):
            continue
        text = _strip_tags(inner)
        if not text:
            continue
        blocks.append({"text": text[:200], "image_url": image_url})
    if not blocks:
        img_with_context = re.findall(r"(<img[^>]+(?:data-original|data-src|src)=['\"]https?://[^'\"]+['\"][^>]*>)(.{0,220})", html_text, flags=re.IGNORECASE | re.DOTALL)
        for img_tag, tail in img_with_context:
            img_match = re.search(r"(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]", img_tag, flags=re.IGNORECASE)
            if not img_match:
                continue
            image_url = img_match.group(1).strip()
            lower = image_url.lower()
            if any(k in lower for k in ["icon", "logo", "sprite", "qrcode", "avatar", "ie-story"]):
                continue
            text = _strip_tags(tail)
            if len(text) < 2:
                continue
            blocks.append({"text": text[:200], "image_url": image_url})
    dedup: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in blocks:
        if row["image_url"] in seen:
            continue
        seen.add(row["image_url"])
        dedup.append(row)
        if len(dedup) >= 80:
            break
    return dedup


def _fill_missing_step_images(draft: dict[str, Any], html_text: str) -> None:
    steps = draft.get("steps") or []
    if not isinstance(steps, list) or not steps:
        return
    cover = draft.get("cover_image_url")
    candidates = _extract_step_image_candidates(html_text)
    if cover:
        candidates = [u for u in candidates if u != cover]
    used = {s.get("image_url") for s in steps if isinstance(s, dict) and isinstance(s.get("image_url"), str) and s.get("image_url")}
    block_pairs = _extract_step_blocks_with_images(html_text)
    block_tokens = [(_tokenize_for_match(x["text"]), x["image_url"]) for x in block_pairs]
    for step in steps:
        if not isinstance(step, dict):
            continue
        existing = step.get("image_url")
        if isinstance(existing, str) and existing.strip():
            continue
        instruction_tokens = _tokenize_for_match(str(step.get("instruction") or ""))
        if not instruction_tokens:
            continue
        best_url = None
        best_score = 0
        for tokens, url in block_tokens:
            if not tokens or url in used:
                continue
            score = len(instruction_tokens & tokens)
            if score > best_score:
                best_score = score
                best_url = url
        if best_url and best_score > 0:
            step["image_url"] = best_url
            used.add(best_url)
    idx = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        existing = step.get("image_url")
        if isinstance(existing, str) and existing.strip():
            continue
        while idx < len(candidates) and candidates[idx] in used:
            idx += 1
        if idx >= len(candidates):
            break
        step["image_url"] = candidates[idx]
        used.add(candidates[idx])
        idx += 1
    media = draft.get("media")
    if not isinstance(media, list):
        media = []
        draft["media"] = media
    media_urls = {m.get("url") for m in media if isinstance(m, dict) and m.get("media_type") == "image" and isinstance(m.get("url"), str)}
    for step in steps:
        if not isinstance(step, dict):
            continue
        img = step.get("image_url")
        if isinstance(img, str) and img and img not in media_urls:
            media.append({"media_type": "image", "url": img})
            media_urls.add(img)


def _ingredient_lines_to_structured(lines: list[str]) -> list[dict[str, Any]]:
    parsed = parse_ingredient_lines_with_llm(lines)
    ingredients: list[dict[str, Any]] = []
    for row in parsed:
        if not isinstance(row, dict):
            continue
        for item in row.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            ingredients.append(
                {
                    "name": name,
                    "amount": item.get("amount"),
                    "unit": item.get("unit"),
                    "note": item.get("note"),
                    "optional": bool(item.get("optional", False)),
                    "is_main": bool(item.get("is_main", False)),
                }
            )
    if ingredients and not any(x["is_main"] for x in ingredients):
        ingredients[0]["is_main"] = True
    return ingredients


def _build_recipe_draft_from_html_fallback(html_text: str, source_url: str) -> dict[str, Any]:
    objs = _extract_json_ld_objects(html_text)
    recipe_obj = _pick_recipe_ld(objs)

    name = None
    description = None
    cover_image_url = None
    tags: list[str] = []
    ingredient_lines: list[str] = []
    steps: list[dict[str, Any]] = []
    cook_time_minutes = 30

    if recipe_obj:
        name = recipe_obj.get("name")
        description = recipe_obj.get("description")
        image = recipe_obj.get("image")
        if isinstance(image, str):
            cover_image_url = image
        elif isinstance(image, list) and image:
            first = image[0]
            if isinstance(first, str):
                cover_image_url = first
            elif isinstance(first, dict):
                cover_image_url = first.get("url")
        elif isinstance(image, dict):
            cover_image_url = image.get("url")
        keywords = recipe_obj.get("keywords")
        if isinstance(keywords, str):
            tags = [t.strip().lower() for t in re.split(r"[,，\s]+", keywords) if t.strip()]
        elif isinstance(keywords, list):
            tags = [str(t).strip().lower() for t in keywords if str(t).strip()]
        raw_ingredients = recipe_obj.get("recipeIngredient") or []
        if isinstance(raw_ingredients, list):
            ingredient_lines = [str(x).strip() for x in raw_ingredients if str(x).strip()]
        raw_instructions = recipe_obj.get("recipeInstructions") or []
        if isinstance(raw_instructions, list):
            for idx, item in enumerate(raw_instructions, start=1):
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        steps.append({"step_order": idx, "instruction": text, "image_url": None})
                elif isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                    image_url = _image_url_from_any(item.get("image"))
                    if text:
                        steps.append({"step_order": idx, "instruction": text, "image_url": image_url})
        cook_time_minutes = _parse_cook_time_minutes(recipe_obj.get("totalTime"))

    if not name:
        name = _extract_meta_content(html_text, "og:title") or _extract_title(html_text) or "Imported Recipe"
    if not description:
        description = _extract_meta_content(html_text, "og:description") or _extract_meta_content(html_text, "description")
    if not cover_image_url:
        cover_image_url = _extract_meta_content(html_text, "og:image")

    if not ingredient_lines:
        maybe_lines = re.findall(r"<li[^>]*>(.*?)</li>", html_text, flags=re.IGNORECASE | re.DOTALL)
        cleaned = [_strip_tags(x) for x in maybe_lines]
        ingredient_lines = [x for x in cleaned if x and len(x) <= 60][:30]

    if not steps:
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_text, flags=re.IGNORECASE | re.DOTALL)
        cleaned = [_strip_tags(x) for x in paragraphs]
        cleaned = [x for x in cleaned if len(x) > 6][:12]
        steps = [{"step_order": i + 1, "instruction": txt, "image_url": None} for i, txt in enumerate(cleaned)]

    ingredients = _ingredient_lines_to_structured([x for x in ingredient_lines if x])
    if ingredients:
        ingredients[0]["is_main"] = True

    main_ingredient = ingredients[0]["name"] if ingredients else None
    method = _infer_cooking_method(name, [s["instruction"] for s in steps])
    difficulty = _guess_difficulty(name, [s["instruction"] for s in steps])

    draft = {
        "name": str(name).strip() or "Imported Recipe",
        "description": description,
        "cook_time_minutes": cook_time_minutes,
        "difficulty": difficulty,
        "tags": tags,
        "source_type": "imported",
        "source_url": source_url,
        "cover_image_url": cover_image_url,
        "main_ingredient": main_ingredient,
        "dish_type": _infer_dish_type(main_ingredient or ""),
        "cooking_method": method,
        "ingredients": ingredients,
        "steps": steps,
        "media": [{"media_type": "image", "url": cover_image_url}] if cover_image_url else [],
    }

    if not draft["ingredients"]:
        raise ValueError("Could not parse ingredients. Please submit HTML from a fully loaded recipe page.")
    if not draft["steps"]:
        raise ValueError("Could not parse steps. Please submit HTML from a fully loaded recipe page.")
    _fill_missing_step_images(draft, html_text)
    return draft


def _build_recipe_draft_from_html(html_text: str, source_url: str) -> tuple[dict[str, Any], str]:
    try:
        draft = parse_recipe_with_llm(html_text=html_text, source_url=source_url)
        _fill_missing_step_images(draft, html_text)
        return draft, "llm"
    except RecipeParserError:
        draft = _build_recipe_draft_from_html_fallback(html_text=html_text, source_url=source_url)
        return draft, "fallback"


def _extract_recipe_id_from_url(url: str) -> int | None:
    m = re.search(r"/recipe/(\d+)/", url)
    if not m:
        return None
    return int(m.group(1))


def _recipe_already_imported(db: Session, recipe_url: str) -> bool:
    normalized = _normalize_recipe_url(recipe_url)
    recipe_id = _extract_recipe_id_from_url(normalized)
    if recipe_id is not None:
        rows = db.execute(select(Recipe.source_url).where(Recipe.source_url.is_not(None))).scalars().all()
        token = f"/recipe/{recipe_id}/"
        for source_url in rows:
            if isinstance(source_url, str) and token in source_url:
                return True
    exact = db.execute(select(Recipe.id).where(Recipe.source_url == normalized)).scalar_one_or_none()
    return exact is not None


def import_recipes_from_html(db: Session, payload: RecipeImportFromHtmlRequest) -> RecipeImportFromHtmlResponse:
    results: list[RecipeImportFromHtmlResult] = []
    for item in payload.recipes:
        source_url = item.source_url.strip()
        if not _is_supported_url(source_url):
            results.append(RecipeImportFromHtmlResult(source_url=source_url, status="failed", message="Only xiachufang.com links are supported for import."))
            continue
        normalized_url = _normalize_recipe_url(source_url)
        if _recipe_already_imported(db, normalized_url):
            results.append(RecipeImportFromHtmlResult(source_url=normalized_url, status="skipped", message="Recipe already imported by source URL."))
            continue
        try:
            draft, parser_mode = _build_recipe_draft_from_html(item.html, normalized_url)
            recipe = create_recipe(db, RecipeCreate(**draft))
            results.append(
                RecipeImportFromHtmlResult(
                    source_url=normalized_url,
                    status="imported",
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    message=f"Imported successfully ({parser_mode}).",
                )
            )
        except IntegrityError:
            db.rollback()
            results.append(RecipeImportFromHtmlResult(source_url=normalized_url, status="skipped", message="Recipe already imported by source URL."))
        except Exception as exc:
            db.rollback()
            results.append(RecipeImportFromHtmlResult(source_url=normalized_url, status="failed", message=f"Import failed: {exc}"))
    return RecipeImportFromHtmlResponse(results=results)


def import_recipe_from_text(db: Session, payload: RecipeImportFromTextRequest) -> RecipeImportFromTextResponse:
    text = payload.text.strip()
    if not text:
        raise ValueError("Recipe text cannot be empty.")

    try:
        draft = parse_recipe_text_with_llm(text)
        recipe = create_recipe(db, RecipeCreate(**draft))
        return RecipeImportFromTextResponse(recipe=recipe, message="Recipe created from text.")
    except RecipeParserError as exc:
        db.rollback()
        raise ValueError(f"Could not parse recipe text: {exc}") from exc
    except Exception:
        db.rollback()
        raise
