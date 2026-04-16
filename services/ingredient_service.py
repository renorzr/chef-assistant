import re
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import load_env_file

load_env_file()


KNOWN_UNITS = [
    "kg", "g", "mg", "ml", "l", "tbsp", "tsp", "cup", "cups",
    "克", "千克", "公斤", "斤", "两", "毫克", "毫升", "升",
    "个", "只", "条", "片", "瓣", "块", "根", "把", "包", "盒", "颗", "朵", "支", "张", "碗", "杯", "罐", "袋", "撮", "滴",
    "勺", "汤匙", "茶匙", "小勺", "大勺",
]

UNIT_PATTERN = "|".join(sorted({re.escape(unit) for unit in KNOWN_UNITS}, key=len, reverse=True))
AMOUNT_PATTERN = r"\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?(?:[~～-]\d+(?:\.\d+)?)?"


def normalize_ingredient_entry(name: str, amount: str | None = None, unit: str | None = None) -> tuple[str, str | None, str | None]:
    raw_name = re.sub(r"\s+", " ", (name or "").strip())
    raw_name = raw_name.strip("，,；;：:·•")
    amount = amount.strip() if isinstance(amount, str) and amount.strip() else None
    unit = unit.strip() if isinstance(unit, str) and unit.strip() else None

    if not raw_name:
        return "", amount, unit

    # Strip trailing explanatory parentheses from the raw ingredient line.
    raw_name = re.sub(r"\s*[（(][^）)]{1,40}[）)]\s*$", "", raw_name).strip()

    range_continuation_match = re.match(
        rf"^(?P<sep>[~～-])(?P<rest_amount>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})\s*(?P<name>.+)$",
        raw_name,
        flags=re.IGNORECASE,
    )
    if range_continuation_match:
        sep = range_continuation_match.group("sep")
        rest_amount = range_continuation_match.group("rest_amount")
        unit = unit or range_continuation_match.group("unit")
        raw_name = range_continuation_match.group("name").strip()
        if amount:
            amount = f"{amount}{sep}{rest_amount}"
        else:
            amount = f"{sep}{rest_amount}"

    colon_match = re.match(r"^(?P<name>.+?)[：:]\s*(?P<tail>.+)$", raw_name)
    if colon_match and not amount and not unit:
        left = colon_match.group("name").strip()
        right = colon_match.group("tail").strip()
        candidate_name, candidate_amount, candidate_unit = normalize_ingredient_entry(left, right, None)
        if candidate_name and candidate_amount:
            return candidate_name, candidate_amount, candidate_unit

    inline_amount_match = re.match(
        rf"^(?:适量|少许)[，,]?(?:也就)?\s*(?:\((?P<bracket>[^)]+)\)|(?P<inline>{AMOUNT_PATTERN}\s*(?:{UNIT_PATTERN})?))(?:吧|左右)?\s*(?P<name>.+)$",
        raw_name,
        flags=re.IGNORECASE,
    )
    if inline_amount_match and not amount and not unit:
        amount_source = (inline_amount_match.group("bracket") or inline_amount_match.group("inline") or "").strip()
        target_name = inline_amount_match.group("name").strip()
        return normalize_ingredient_entry(target_name, amount_source, None)

    if not amount and not unit:
        suffix_match = re.match(
            rf"^(?P<name>.+?)\s+(?P<amount>{AMOUNT_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?$",
            raw_name,
            flags=re.IGNORECASE,
        )
        if suffix_match:
            raw_name = suffix_match.group("name").strip()
            amount = suffix_match.group("amount") or None
            unit = suffix_match.group("unit") or None
        else:
            suffix_match = re.match(
                rf"^(?P<name>.+?)\s*(?P<amount>{AMOUNT_PATTERN})\s*(?P<unit>{UNIT_PATTERN})$",
                raw_name,
                flags=re.IGNORECASE,
            )
            if suffix_match:
                raw_name = suffix_match.group("name").strip()
                amount = suffix_match.group("amount") or None
                unit = suffix_match.group("unit") or None
            else:
                prefix_with_unit_match = re.match(
                    rf"^(?P<amount>{AMOUNT_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\s*(?P<name>.+)$",
                    raw_name,
                    flags=re.IGNORECASE,
                )
                if prefix_with_unit_match:
                    raw_name = prefix_with_unit_match.group("name").strip()
                    amount = prefix_with_unit_match.group("amount") or None
                    unit = prefix_with_unit_match.group("unit") or None
                else:
                    prefix_match = re.match(
                        rf"^(?P<amount>{AMOUNT_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?\s*(?P<name>.+)$",
                        raw_name,
                        flags=re.IGNORECASE,
                    )
                    if prefix_match:
                        raw_name = prefix_match.group("name").strip()
                        amount = prefix_match.group("amount") or None
                        unit = prefix_match.group("unit") or None

    if amount and not unit:
        amount_value = re.sub(r"\s+", "", amount)
        embedded = re.match(rf"^(?P<amount>{AMOUNT_PATTERN})(?P<unit>{UNIT_PATTERN})?(?:左右|吧)?$", amount_value, flags=re.IGNORECASE)
        if embedded:
            amount = embedded.group("amount") or amount
            unit = embedded.group("unit") or unit

    normalized_name = re.sub(r"\s+", " ", raw_name).strip("，,；;：:·•").lower()
    return normalized_name, amount, unit


def parse_ingredient_lines_with_llm(lines: list[str]) -> list[dict[str, Any]]:
    base_url = os.getenv("RECIPE_PARSER_BASE_URL", "").strip()
    api_key = os.getenv("RECIPE_PARSER_API_KEY", "").strip()
    model = os.getenv("RECIPE_PARSER_MODEL", "").strip()
    timeout_seconds = float(os.getenv("RECIPE_PARSER_TIMEOUT_SECONDS", "30"))

    if not lines:
        return []
    if not base_url or not api_key or not model:
        return [
            {
                "source": line,
                "items": [
                    {
                        "name": normalize_ingredient_entry(line)[0] or line.strip(),
                        "amount": normalize_ingredient_entry(line)[1],
                        "unit": normalize_ingredient_entry(line)[2],
                        "note": None,
                        "optional": False,
                        "is_main": False,
                    }
                ],
            }
            for line in lines
            if line and line.strip()
        ]

    schema_hint = {
        "results": [
            {
                "source": "original line",
                "items": [
                    {
                        "name": "canonical ingredient name only",
                        "amount": "string|null",
                        "unit": "string|null",
                        "note": "string|null",
                        "optional": "boolean",
                        "is_main": "boolean"
                    }
                ]
            }
        ]
    }

    prompt = (
        "Parse the ingredient lines from one recipe into structured ingredients. "
        "Return strictly valid JSON only. "
        f"Schema: {json.dumps(schema_hint, ensure_ascii=False)}. "
        "Rules: ingredient names must be canonical names only; quantity/units should be split out; "
        "notes like '按人数调整' or '按口味调整' go into note; optional ingredients should set optional=true; "
        "one source line may expand into multiple items; if the line is vague, keep the ingredient but put the vagueness in note."
    )

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a precise ingredient extraction engine."},
            {"role": "user", "content": f"Ingredient lines:\n{json.dumps(lines, ensure_ascii=False)}"},
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
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
        data = json.loads(content)
        results = data.get("results", []) if isinstance(data, dict) else []
    except (HTTPError, URLError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        results = []

    if not results:
        fallback = []
        for line in lines:
            if not line or not line.strip():
                continue
            name, amount, unit = normalize_ingredient_entry(line)
            fallback.append(
                {
                    "source": line,
                    "items": [
                        {
                            "name": name or line.strip(),
                            "amount": amount,
                            "unit": unit,
                            "note": None,
                            "optional": False,
                            "is_main": False,
                        }
                    ],
                }
            )
        return fallback

    normalized_results = []
    for row in results:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        items = []
        for item in row.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            name, amount, unit = normalize_ingredient_entry(
                str(item.get("name") or ""),
                item.get("amount"),
                item.get("unit"),
            )
            if not name:
                continue
            items.append(
                {
                    "name": name,
                    "amount": amount,
                    "unit": unit,
                    "note": str(item.get("note") or "").strip() or None,
                    "optional": bool(item.get("optional", False)),
                    "is_main": bool(item.get("is_main", False)),
                }
            )
        if items:
            normalized_results.append({"source": source, "items": items})

    return normalized_results
