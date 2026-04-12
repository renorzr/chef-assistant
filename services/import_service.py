import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import RecipeImportJob, Recipe, XiachufangRecommendedRun, XiachufangRecommendedRunItem
from schemas import (
    RecipeCreate,
    RecipeImportStatusResponse,
    RecipeImportPreviewResponse,
    RecipeImportCommitResponse,
    XiachufangRecommendedRunResponse,
    XiachufangRecommendedRunItemsResponse,
    XiachufangRecommendedRunItemRead,
)
from services.recipe_service import create_recipe
from services.recipe_parser_llm import parse_recipe_with_llm, RecipeParserError


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


def _extract_recommended_recipe_urls(homepage_html: str, homepage_url: str, max_links: int) -> list[str]:
    hrefs = re.findall(r"href=['\"]([^'\"]+)['\"]", homepage_html, flags=re.IGNORECASE)
    out: list[str] = []
    seen: set[str] = set()

    for href in hrefs:
        full = urljoin(homepage_url, href)
        normalized = _normalize_recipe_url(full)
        if not re.match(r"^https://www\.xiachufang\.com/recipe/\d+/$", normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= max_links:
            break

    return out


def _make_recommended_run_status(run: XiachufangRecommendedRun) -> XiachufangRecommendedRunResponse:
    return XiachufangRecommendedRunResponse(
        run_id=run.id,
        homepage_url=run.homepage_url,
        max_links=run.max_links,
        auto_commit=bool(run.auto_commit),
        status=run.status,
        message=run.message,
        next_action=run.next_action,
        requires_user_intervention=run.status in {"challenge_required", "awaiting_user_input"},
        discovered_count=run.discovered_count,
        queued_count=run.queued_count,
        imported_count=run.imported_count,
        failed_count=run.failed_count,
        skipped_count=run.skipped_count,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


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
        m = re.search(
            r"(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]",
            tag,
            flags=re.IGNORECASE,
        )
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
    word_tokens = re.findall(r"[a-z0-9]+", lower)
    cjk_tokens = re.findall(r"[\u4e00-\u9fff]", lower)
    return set(word_tokens + cjk_tokens)


def _extract_step_blocks_with_images(html_text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []

    pattern = re.compile(
        r"<(li|div|section)[^>]*(?:step|zuofa|method|process|步骤|做法)[^>]*>(.*?)</\1>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for _, inner in pattern.findall(html_text):
        img_match = re.search(
            r"<img[^>]+(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]",
            inner,
            flags=re.IGNORECASE,
        )
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

    # fallback: infer from image-nearby paragraph text
    if not blocks:
        img_with_context = re.findall(
            r"(<img[^>]+(?:data-original|data-src|src)=['\"]https?://[^'\"]+['\"][^>]*>)(.{0,220})",
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for img_tag, tail in img_with_context:
            img_match = re.search(
                r"(?:data-original|data-src|src)=['\"](https?://[^'\"]+)['\"]",
                img_tag,
                flags=re.IGNORECASE,
            )
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

    # dedupe by image url
    dedup: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in blocks:
        url = row["image_url"]
        if url in seen:
            continue
        seen.add(url)
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

    used = {
        s.get("image_url")
        for s in steps
        if isinstance(s, dict) and isinstance(s.get("image_url"), str) and s.get("image_url")
    }

    block_pairs = _extract_step_blocks_with_images(html_text)
    block_tokens = [(_tokenize_for_match(x["text"]), x["image_url"]) for x in block_pairs]

    # phase 1: text proximity matching (best effort)
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

    # phase 2: sequential fallback
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

    media_urls = {
        m.get("url")
        for m in media
        if isinstance(m, dict) and m.get("media_type") == "image" and isinstance(m.get("url"), str)
    }

    for step in steps:
        if not isinstance(step, dict):
            continue
        img = step.get("image_url")
        if isinstance(img, str) and img and img not in media_urls:
            media.append({"media_type": "image", "url": img})
            media_urls.add(img)


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


def _import_one_recipe_url(
    db: Session,
    recipe_url: str,
    cookie_header: str | None,
    auto_commit: bool,
) -> tuple[str, int | None, int | None, str]:
    recipe_url = _normalize_recipe_url(recipe_url)

    if _recipe_already_imported(db, recipe_url):
        return "skipped", None, None, "Recipe already imported by source URL."

    job = RecipeImportJob(
        source_url=recipe_url,
        source_domain=SUPPORTED_DOMAIN,
        status="pending",
        message="Import job created from recommended list.",
        next_action="auto_fetch",
        cookie_header=cookie_header.strip() if cookie_header else None,
    )
    db.add(job)
    db.flush()

    _run_import_attempt(job)

    if job.status != "ready_to_commit":
        return "failed", job.id, None, job.message or "Import parsing failed."

    if not auto_commit:
        return "parsed", job.id, None, "Parsed and waiting for manual commit."

    recipe_payload = RecipeCreate(**job.parsed_recipe)
    recipe = create_recipe(db, recipe_payload)

    job.status = "completed"
    job.next_action = None
    job.message = "Import committed successfully from recommended list."

    return "completed", job.id, recipe.id, "Imported and committed."


def _reset_run_counters(run: XiachufangRecommendedRun) -> None:
    run.discovered_count = 0
    run.queued_count = 0
    run.imported_count = 0
    run.failed_count = 0
    run.skipped_count = 0


def _run_recommended_import_attempt(
    db: Session,
    run: XiachufangRecommendedRun,
    max_links: int,
    auto_commit: bool,
) -> None:
    run.status = "fetching"
    run.next_action = None
    run.message = "Fetching Xiachufang homepage..."
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = None
    _reset_run_counters(run)
    run.items.clear()
    db.flush()

    try:
        homepage_html = _fetch_url_html(run.homepage_url, run.cookie_header)
    except HTTPError as exc:
        if exc.code in {403, 429}:
            run.status = "challenge_required"
            run.next_action = "resume_with_cookies_or_submit_html"
            run.message = (
                "Homepage blocked automated access. Complete verification in browser, "
                "then resume with cookies or submit homepage HTML."
            )
            run.finished_at = datetime.now(timezone.utc)
            return
        run.status = "failed"
        run.message = f"Homepage fetch failed with HTTP error {exc.code}."
        run.next_action = None
        run.finished_at = datetime.now(timezone.utc)
        return
    except URLError:
        run.status = "failed"
        run.message = "Homepage fetch failed due to network error."
        run.next_action = None
        run.finished_at = datetime.now(timezone.utc)
        return
    except Exception as exc:
        run.status = "failed"
        run.message = f"Homepage fetch failed: {exc}"
        run.next_action = None
        run.finished_at = datetime.now(timezone.utc)
        return

    run.homepage_html = homepage_html

    if _detect_challenge(homepage_html):
        run.status = "challenge_required"
        run.next_action = "resume_with_cookies_or_submit_html"
        run.message = (
            "Homepage requires human verification. Complete challenge in browser, then "
            "resume with cookies or submit homepage HTML."
        )
        run.finished_at = datetime.now(timezone.utc)
        return

    links = _extract_recommended_recipe_urls(homepage_html, run.homepage_url, max_links=max_links)
    run.discovered_count = len(links)

    if not links:
        run.status = "failed"
        run.next_action = None
        run.message = "No recommended recipe links found on homepage."
        run.finished_at = datetime.now(timezone.utc)
        return

    run.status = "importing"
    run.message = f"Importing {len(links)} recommended recipes..."
    run.queued_count = len(links)

    for recipe_url in links:
        item = XiachufangRecommendedRunItem(
            run_id=run.id,
            recipe_url=recipe_url,
            status="processing",
            message="Import in progress.",
        )
        db.add(item)
        db.flush()

        status, import_job_id, recipe_id, message = _import_one_recipe_url(
            db=db,
            recipe_url=recipe_url,
            cookie_header=run.cookie_header,
            auto_commit=auto_commit,
        )

        item.status = status
        item.message = message
        item.import_job_id = import_job_id
        item.recipe_id = recipe_id

        if status == "completed":
            run.imported_count += 1
        elif status == "skipped":
            run.skipped_count += 1
        else:
            run.failed_count += 1

    run.finished_at = datetime.now(timezone.utc)
    run.next_action = None
    run.status = "completed"
    run.message = (
        f"Recommended import finished: imported={run.imported_count}, "
        f"skipped={run.skipped_count}, failed={run.failed_count}."
    )


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
        draft, parser_mode = _build_recipe_draft_from_html(html_text, job.source_url)
    except Exception as exc:
        job.status = "awaiting_user_input"
        job.next_action = "submit_html"
        job.message = f"Auto-parse failed: {exc}. Please submit full recipe HTML manually."
        return

    job.parsed_recipe = draft
    job.status = "ready_to_commit"
    job.next_action = "preview_or_commit"
    job.message = f"Recipe parsed successfully ({parser_mode}). You can preview and commit."


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
        draft, parser_mode = _build_recipe_draft_from_html(html_text, job.source_url)
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
    job.message = f"Recipe parsed successfully from submitted HTML ({parser_mode})."
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


def create_recommended_import_run(
    db: Session,
    homepage_url: str,
    max_links: int,
    auto_commit: bool,
    cookie_header: str | None = None,
) -> XiachufangRecommendedRunResponse:
    homepage_url = (homepage_url or "https://www.xiachufang.com/").strip()
    max_links = max(1, min(max_links, 200))
    if not _is_supported_url(homepage_url):
        raise ValueError("Only xiachufang.com homepage URL is supported.")

    run = XiachufangRecommendedRun(
        homepage_url=homepage_url,
        max_links=max_links,
        auto_commit=1 if auto_commit else 0,
        status="pending",
        message="Recommended import run created.",
        next_action="auto_fetch",
        cookie_header=cookie_header.strip() if cookie_header else None,
    )
    db.add(run)
    db.flush()

    _run_recommended_import_attempt(db, run=run, max_links=max_links, auto_commit=auto_commit)
    db.commit()
    db.refresh(run)
    return _make_recommended_run_status(run)


def get_recommended_import_run_status(db: Session, run_id: int) -> XiachufangRecommendedRunResponse:
    run = db.get(XiachufangRecommendedRun, run_id)
    if not run:
        raise ValueError("Recommended import run not found.")
    return _make_recommended_run_status(run)


def list_recommended_import_run_items(db: Session, run_id: int) -> XiachufangRecommendedRunItemsResponse:
    run = db.get(XiachufangRecommendedRun, run_id)
    if not run:
        raise ValueError("Recommended import run not found.")

    rows = db.execute(
        select(XiachufangRecommendedRunItem)
        .where(XiachufangRecommendedRunItem.run_id == run_id)
        .order_by(XiachufangRecommendedRunItem.id.asc())
    ).scalars().all()

    return XiachufangRecommendedRunItemsResponse(
        run_id=run_id,
        items=[
            XiachufangRecommendedRunItemRead(
                id=row.id,
                recipe_url=row.recipe_url,
                status=row.status,
                message=row.message,
                import_job_id=row.import_job_id,
                recipe_id=row.recipe_id,
            )
            for row in rows
        ],
    )


def resume_recommended_import_with_cookies(
    db: Session,
    run_id: int,
    cookie_header: str,
) -> XiachufangRecommendedRunResponse:
    run = db.get(XiachufangRecommendedRun, run_id)
    if not run:
        raise ValueError("Recommended import run not found.")

    run.cookie_header = cookie_header.strip()
    _run_recommended_import_attempt(
        db,
        run=run,
        max_links=run.max_links,
        auto_commit=bool(run.auto_commit),
    )
    db.commit()
    db.refresh(run)
    return _make_recommended_run_status(run)


def submit_recommended_homepage_html(
    db: Session,
    run_id: int,
    html_text: str,
) -> XiachufangRecommendedRunResponse:
    run = db.get(XiachufangRecommendedRun, run_id)
    if not run:
        raise ValueError("Recommended import run not found.")

    run.homepage_html = html_text
    if _detect_challenge(html_text):
        run.status = "awaiting_user_input"
        run.next_action = "submit_html"
        run.message = "Submitted homepage HTML still contains challenge content."
        db.commit()
        db.refresh(run)
        return _make_recommended_run_status(run)

    links = _extract_recommended_recipe_urls(html_text, run.homepage_url, max_links=run.max_links)
    run.discovered_count = len(links)
    run.queued_count = len(links)
    run.imported_count = 0
    run.failed_count = 0
    run.skipped_count = 0
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = None
    run.items.clear()
    db.flush()

    if not links:
        run.status = "failed"
        run.next_action = None
        run.message = "No recommended recipe links found in submitted homepage HTML."
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return _make_recommended_run_status(run)

    run.status = "importing"
    run.message = f"Importing {len(links)} recommended recipes from submitted HTML..."

    for recipe_url in links:
        item = XiachufangRecommendedRunItem(
            run_id=run.id,
            recipe_url=recipe_url,
            status="processing",
            message="Import in progress.",
        )
        db.add(item)
        db.flush()

        status, import_job_id, recipe_id, message = _import_one_recipe_url(
            db=db,
            recipe_url=recipe_url,
            cookie_header=run.cookie_header,
            auto_commit=bool(run.auto_commit),
        )
        item.status = status
        item.message = message
        item.import_job_id = import_job_id
        item.recipe_id = recipe_id

        if status == "completed":
            run.imported_count += 1
        elif status == "skipped":
            run.skipped_count += 1
        else:
            run.failed_count += 1

    run.status = "completed"
    run.next_action = None
    run.finished_at = datetime.now(timezone.utc)
    run.message = (
        f"Recommended import finished: imported={run.imported_count}, "
        f"skipped={run.skipped_count}, failed={run.failed_count}."
    )
    db.commit()
    db.refresh(run)
    return _make_recommended_run_status(run)


def get_recommended_import_daily_config() -> dict[str, Any]:
    enabled = os.getenv("XCF_RECOMMENDED_DAILY_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    daily_time = os.getenv("XCF_RECOMMENDED_DAILY_TIME", "06:00").strip()
    timezone_name = os.getenv("XCF_RECOMMENDED_DAILY_TZ", "Asia/Shanghai").strip()
    max_links = int(os.getenv("XCF_RECOMMENDED_MAX_LINKS", "30"))
    auto_commit = os.getenv("XCF_RECOMMENDED_AUTO_COMMIT", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    homepage_url = os.getenv("XCF_RECOMMENDED_HOMEPAGE_URL", "https://www.xiachufang.com/").strip()
    cookie_header = os.getenv("XCF_RECOMMENDED_COOKIE", "").strip() or None

    return {
        "enabled": enabled,
        "daily_time": daily_time,
        "timezone_name": timezone_name,
        "max_links": max(1, min(max_links, 200)),
        "auto_commit": auto_commit,
        "homepage_url": homepage_url,
        "cookie_header": cookie_header,
    }


def run_recommended_import_daily_once(db: Session) -> XiachufangRecommendedRunResponse:
    cfg = get_recommended_import_daily_config()
    return create_recommended_import_run(
        db=db,
        homepage_url=cfg["homepage_url"],
        max_links=cfg["max_links"],
        auto_commit=cfg["auto_commit"],
        cookie_header=cfg["cookie_header"],
    )
