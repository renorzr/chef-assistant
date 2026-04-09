import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import load_env_file

load_env_file()


class RecipeParserError(Exception):
    pass


def _compact_text_from_html(html_text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:12000]


def _normalize_draft(draft: dict[str, Any], source_url: str) -> dict[str, Any]:
    name = str(draft.get("name") or "Imported Recipe").strip()
    description = draft.get("description")
    cook_time_minutes = int(draft.get("cook_time_minutes") or 30)
    cook_time_minutes = max(1, cook_time_minutes)

    difficulty = str(draft.get("difficulty") or "medium").strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    dish_type = str(draft.get("dish_type") or "other").strip().lower()
    if dish_type not in {"meat", "vegetable", "other"}:
        dish_type = "other"

    cooking_method = str(draft.get("cooking_method") or "other").strip().lower()

    tags = [str(x).strip().lower() for x in (draft.get("tags") or []) if str(x).strip()]

    cover_image_url = draft.get("cover_image_url")
    source_type = "imported"

    ingredients_raw = draft.get("ingredients") or []
    ingredients: list[dict[str, Any]] = []
    for row in ingredients_raw:
        if not isinstance(row, dict):
            continue
        ing_name = str(row.get("name") or "").strip()
        if not ing_name:
            continue
        ingredients.append(
            {
                "name": ing_name,
                "amount": row.get("amount"),
                "unit": row.get("unit"),
                "is_main": bool(row.get("is_main", False)),
            }
        )

    if ingredients and not any(x["is_main"] for x in ingredients):
        ingredients[0]["is_main"] = True

    steps_raw = draft.get("steps") or []
    steps: list[dict[str, Any]] = []
    for idx, row in enumerate(steps_raw, start=1):
        if not isinstance(row, dict):
            continue
        instruction = str(row.get("instruction") or "").strip()
        if not instruction:
            continue
        order = row.get("step_order")
        if not isinstance(order, int) or order < 1:
            order = idx
        steps.append(
            {
                "step_order": order,
                "instruction": instruction,
                "image_url": row.get("image_url"),
            }
        )

    steps.sort(key=lambda x: x["step_order"])

    media_raw = draft.get("media") or []
    media: list[dict[str, Any]] = []
    for row in media_raw:
        if not isinstance(row, dict):
            continue
        m_type = str(row.get("media_type") or "").strip().lower()
        url = str(row.get("url") or "").strip()
        if m_type in {"image", "video"} and url:
            media.append({"media_type": m_type, "url": url})

    if cover_image_url and not any(m["media_type"] == "image" and m["url"] == cover_image_url for m in media):
        media.append({"media_type": "image", "url": cover_image_url})

    main_ingredient = draft.get("main_ingredient")
    if not main_ingredient and ingredients:
        main_ingredient = ingredients[0]["name"]

    normalized = {
        "name": name,
        "description": description,
        "cook_time_minutes": cook_time_minutes,
        "difficulty": difficulty,
        "tags": tags,
        "source_type": source_type,
        "source_url": source_url,
        "cover_image_url": cover_image_url,
        "main_ingredient": main_ingredient,
        "dish_type": dish_type,
        "cooking_method": cooking_method,
        "ingredients": ingredients,
        "steps": steps,
        "media": media,
    }

    if not normalized["ingredients"]:
        raise RecipeParserError("LLM parser did not extract ingredients.")
    if not normalized["steps"]:
        raise RecipeParserError("LLM parser did not extract steps.")

    return normalized


def parse_recipe_with_llm(html_text: str, source_url: str) -> dict[str, Any]:
    provider = os.getenv("RECIPE_PARSER_PROVIDER", "openai_compatible").strip().lower()
    if provider != "openai_compatible":
        raise RecipeParserError("Unsupported RECIPE_PARSER_PROVIDER.")

    base_url = os.getenv("RECIPE_PARSER_BASE_URL", "").strip()
    api_key = os.getenv("RECIPE_PARSER_API_KEY", "").strip()
    model = os.getenv("RECIPE_PARSER_MODEL", "").strip()
    timeout_seconds = float(os.getenv("RECIPE_PARSER_TIMEOUT_SECONDS", "30"))

    if not base_url or not api_key or not model:
        raise RecipeParserError(
            "Missing parser config: RECIPE_PARSER_BASE_URL / RECIPE_PARSER_API_KEY / RECIPE_PARSER_MODEL."
        )

    compact_text = _compact_text_from_html(html_text)

    schema_hint = {
        "name": "string",
        "description": "string|null",
        "cook_time_minutes": "integer",
        "difficulty": "easy|medium|hard",
        "tags": ["string"],
        "cover_image_url": "string|null",
        "main_ingredient": "string|null",
        "dish_type": "meat|vegetable|other",
        "cooking_method": "string",
        "ingredients": [
            {"name": "string", "amount": "string|null", "unit": "string|null", "is_main": "boolean"}
        ],
        "steps": [{"step_order": "integer", "instruction": "string", "image_url": "string|null"}],
        "media": [{"media_type": "image|video", "url": "string"}],
    }

    prompt = (
        "Extract ONE recipe from the given Xiachufang page content. "
        "Return strictly valid JSON only, with keys matching this schema: "
        f"{json.dumps(schema_hint, ensure_ascii=False)}. "
        "If values are unknown, use null or reasonable defaults. "
        "Do not include markdown fences or extra text."
    )

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a precise recipe extraction engine."},
            {
                "role": "user",
                "content": (
                    f"Source URL: {source_url}\n"
                    "Page text (cleaned from html):\n"
                    f"{compact_text}"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    req = Request(
        url=f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        raise RecipeParserError(f"LLM parser HTTP error {exc.code}: {err_body[:300]}") from exc
    except URLError as exc:
        raise RecipeParserError(f"LLM parser network error: {exc}") from exc
    except Exception as exc:
        raise RecipeParserError(f"LLM parser request failed: {exc}") from exc

    try:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
        draft = json.loads(content)
        if not isinstance(draft, dict):
            raise ValueError("content is not object")
    except Exception as exc:
        raise RecipeParserError("LLM parser response is not valid JSON recipe object.") from exc

    return _normalize_draft(draft, source_url=source_url)
