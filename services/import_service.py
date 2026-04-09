import json
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from sqlalchemy.orm import Session

from models import RecipeImportJob
from schemas import (
    RecipeCreate,
    RecipeImportStatusResponse,
    RecipeImportPreviewResponse,
    RecipeImportCommitResponse,
)
from services.recipe_service import create_recipe


SUPPORTED_DOMAIN = "xiachufang.com"


def _is_supported_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower()
    return host == SUPPORTED_DOMAIN or host.endswith(f".{SUPPORTED_DOMAIN}")


def _make_status(job: RecipeImportJob) -> RecipeImportStatusResponse:
    return RecipeImportStatusResponse(
        job_id=job.id,
        source_url=job.source_url,
        status=job.status,
        message=job.message,
        next_action=job.next_action,
        requires_user_intervention=job.status in {"challenge_required", "awaiting_user_input"},
    )


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

        candidates: list[Any]
        if isinstance(payload, list):
            candidates = payload
        else:
            candidates = [payload]

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
            type_tokens = {str(x).lower() for x in t}
            if "recipe" in type_tokens:
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
            hours_match = re.search(r"(\d+)H", s)
            mins_match = re.search(r"(\d+)M", s)
            hours = int(hours_match.group(1)) if hours_match else 0
            mins = int(mins_match.group(1)) if mins_match else 0
            total = hours * 60 + mins
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


def _ingredient_line_to_struct(line: str) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", line).strip()
    return {
        "name": clean,
        "amount": None,
        "unit": None,
        "is_main": False,
    }


def _detect_challenge(html_text: str) -> bool:
    text = (html_text or "").lower()
    markers = [
        "captcha",
        "geetest",
        "人机验证",
        "滑动验证",
        "请完成验证",
        "security check",
        "robot",
    ]
    return any(m in text for m in markers)


def _build_recipe_draft_from_html(html_text: str, source_url: str) -> dict[str, Any]:
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
                    image_url = item.get("image") if isinstance(item.get("image"), str) else None
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
        ingredient_lines = [x for x in cleaned if x and len(x) <= 40][:20]

    if not steps:
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_text, flags=re.IGNORECASE | re.DOTALL)
        cleaned = [_strip_tags(x) for x in paragraphs]
        cleaned = [x for x in cleaned if len(x) > 6][:12]
        steps = [{"step_order": i + 1, "instruction": txt, "image_url": None} for i, txt in enumerate(cleaned)]

    ingredients = [_ingredient_line_to_struct(x) for x in ingredient_lines if x]
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

    return draft


def _fetch_url_html(url: str, cookie_header: str | None = None) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header.strip()

    req = Request(url=url, headers=headers, method="GET")
    with urlopen(req, timeout=12) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def _run_import_attempt(job: RecipeImportJob) -> None:
    job.status = "fetching"
    job.next_action = None
    job.message = "Fetching source page..."

    try:
        html_text = _fetch_url_html(job.source_url, job.cookie_header)
    except HTTPError as exc:
        if exc.code in {403, 429}:
            job.status = "challenge_required"
            job.next_action = "resume_with_cookies_or_submit_html"
            job.message = (
                "Source website blocked automated access. Complete verification in browser, "
                "then resume with cookies or submit page HTML."
            )
            return
        job.status = "failed"
        job.next_action = None
        job.message = f"Import failed with HTTP error {exc.code}."
        return
    except URLError:
        job.status = "failed"
        job.next_action = None
        job.message = "Import failed due to network error while fetching source page."
        return
    except Exception as exc:
        job.status = "failed"
        job.next_action = None
        job.message = f"Import failed while fetching source page: {exc}"
        return

    job.fetched_html = html_text
    if _detect_challenge(html_text):
        job.status = "challenge_required"
        job.next_action = "resume_with_cookies_or_submit_html"
        job.message = (
            "Human verification detected. Complete challenge in browser, then submit cookies "
            "or submit recipe HTML manually."
        )
        return

    try:
        draft = _build_recipe_draft_from_html(html_text, job.source_url)
    except Exception as exc:
        job.status = "awaiting_user_input"
        job.next_action = "submit_html"
        job.message = f"Auto-parse failed: {exc}. Please submit full recipe HTML manually."
        return

    job.parsed_recipe = draft
    job.status = "ready_to_commit"
    job.next_action = "preview_or_commit"
    job.message = "Recipe parsed successfully. You can preview and commit."


def create_import_job(db: Session, source_url: str) -> RecipeImportStatusResponse:
    if not _is_supported_url(source_url):
        raise ValueError("Only xiachufang.com links are supported for import.")

    job = RecipeImportJob(
        source_url=source_url.strip(),
        source_domain=SUPPORTED_DOMAIN,
        status="pending",
        message="Import job created.",
        next_action="auto_fetch",
    )
    db.add(job)
    db.flush()

    _run_import_attempt(job)
    db.commit()
    db.refresh(job)
    return _make_status(job)


def get_import_job_status(db: Session, job_id: int) -> RecipeImportStatusResponse:
    job = db.get(RecipeImportJob, job_id)
    if not job:
        raise ValueError("Import job not found.")
    return _make_status(job)


def resume_import_with_cookies(db: Session, job_id: int, cookie_header: str) -> RecipeImportStatusResponse:
    job = db.get(RecipeImportJob, job_id)
    if not job:
        raise ValueError("Import job not found.")

    job.cookie_header = cookie_header.strip()
    _run_import_attempt(job)
    db.commit()
    db.refresh(job)
    return _make_status(job)


def submit_import_html(db: Session, job_id: int, html_text: str) -> RecipeImportStatusResponse:
    job = db.get(RecipeImportJob, job_id)
    if not job:
        raise ValueError("Import job not found.")

    job.fetched_html = html_text
    job.status = "parsing"
    job.next_action = None
    job.message = "Parsing submitted HTML..."

    try:
        draft = _build_recipe_draft_from_html(html_text, job.source_url)
    except Exception as exc:
        job.status = "awaiting_user_input"
        job.next_action = "submit_html"
        job.message = f"Parse failed: {exc}. Please submit cleaner HTML from recipe detail page."
        db.commit()
        db.refresh(job)
        return _make_status(job)

    job.parsed_recipe = draft
    job.status = "ready_to_commit"
    job.next_action = "preview_or_commit"
    job.message = "Recipe parsed successfully from submitted HTML."
    db.commit()
    db.refresh(job)
    return _make_status(job)


def get_import_preview(db: Session, job_id: int) -> RecipeImportPreviewResponse:
    job = db.get(RecipeImportJob, job_id)
    if not job:
        raise ValueError("Import job not found.")
    if not job.parsed_recipe:
        raise ValueError("No parsed recipe available yet. Complete import parsing first.")

    recipe = RecipeCreate(**job.parsed_recipe)
    return RecipeImportPreviewResponse(job_id=job.id, status=job.status, recipe=recipe)


def commit_import_job(db: Session, job_id: int) -> RecipeImportCommitResponse:
    job = db.get(RecipeImportJob, job_id)
    if not job:
        raise ValueError("Import job not found.")
    if not job.parsed_recipe:
        raise ValueError("No parsed recipe to commit.")

    recipe_payload = RecipeCreate(**job.parsed_recipe)
    recipe = create_recipe(db, recipe_payload)

    job.status = "completed"
    job.next_action = None
    job.message = "Import committed successfully."
    db.commit()
    db.refresh(job)

    return RecipeImportCommitResponse(job_id=job.id, status=job.status, recipe=recipe)
