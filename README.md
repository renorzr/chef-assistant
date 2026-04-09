# AI Cooking Assistant MVP

FastAPI + SQLite/PostgreSQL backend for recipe management, menu generation, vector/hybrid search, and importing recipes from links (including challenge-aware flow for Xiachufang).

## Features

- Recipe CRUD
  - Create recipe: `POST /recipes`
  - List recipes: `GET /recipes`
  - Get recipe detail: `GET /recipes/{id}`
  - Update recipe: `PUT /recipes/{id}`
  - Delete recipe: `DELETE /recipes/{id}`
- Menu planning
  - Generate menu: `POST /menu/generate`
  - Rules included: main ingredient diversity, meat+vegetable balance, cooking method diversity, available ingredient preference, simple/short-time preference
- Search
  - Vector search: `POST /recipes/search/vector`
  - Hybrid search (keyword + vector rerank): `POST /recipes/search/hybrid`
- Import from link (Xiachufang)
  - Challenge-aware state machine with user intervention (cookies or manual HTML)

## Tech Stack

- Python + FastAPI
- SQLAlchemy ORM
- Default DB: SQLite (`chef_assistant.db`)
- Optional DB: PostgreSQL via `DATABASE_URL`

## Quick Start

### 1) Create virtualenv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run service

```bash
uvicorn main:app --reload
```

### 3) Open API docs

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI spec: `http://127.0.0.1:8000/openapi.json`

## Environment Variables

- `DATABASE_URL` (optional)
  - Default: `sqlite:///./chef_assistant.db`
  - PostgreSQL example:

```bash
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/chef_assistant"
```

## Core API Examples

### Create recipe

```bash
curl -X POST "http://127.0.0.1:8000/recipes" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Garlic Shrimp",
    "description": "Quick pan shrimp",
    "cook_time_minutes": 20,
    "difficulty": "easy",
    "tags": ["seafood", "quick"],
    "source_type": "user",
    "cover_image_url": "https://example.com/cover.jpg",
    "main_ingredient": "shrimp",
    "dish_type": "meat",
    "cooking_method": "fry",
    "ingredients": [
      {"name": "shrimp", "amount": "300", "unit": "g", "is_main": true},
      {"name": "garlic", "amount": "3", "unit": "cloves", "is_main": false}
    ],
    "steps": [
      {"step_order": 1, "instruction": "Prep ingredients", "image_url": "https://example.com/s1.jpg"},
      {"step_order": 2, "instruction": "Stir fry shrimp", "image_url": "https://example.com/s2.jpg"}
    ],
    "media": [
      {"media_type": "video", "url": "https://example.com/demo.mp4"}
    ]
  }'
```

### Generate menu

```bash
curl -X POST "http://127.0.0.1:8000/menu/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "people_count": 3,
    "dish_count": 3,
    "preferences": ["fish"],
    "available_ingredients": ["egg", "garlic", "tomato"],
    "constraints": ["simple"]
  }'
```

### Hybrid search

```bash
curl -X POST "http://127.0.0.1:8000/recipes/search/hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "quick fish soup",
    "top_k": 5,
    "semantic_weight": 0.7
  }'
```

## Xiachufang Import Flow (Challenge-Aware)

### Step 1: Create import job

```bash
curl -X POST "http://127.0.0.1:8000/recipes/import" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.xiachufang.com/recipe/104000000/"}'
```

If anti-bot is triggered, you will get status like `challenge_required`.

### Step 2A: Resume with cookie (recommended)

After solving challenge in your browser, copy request cookie and resume:

```bash
curl -X POST "http://127.0.0.1:8000/recipes/import/{job_id}/resume-with-cookies" \
  -H "Content-Type: application/json" \
  -d '{"cookie":"your_xiachufang_cookie_header"}'
```

### Step 2B: Manual HTML fallback

If cookie flow still fails, submit full recipe HTML manually:

```bash
curl -X POST "http://127.0.0.1:8000/recipes/import/{job_id}/submit-html" \
  -H "Content-Type: application/json" \
  -d '{"html":"<html>...</html>"}'
```

### Step 3: Preview parsed recipe

```bash
curl "http://127.0.0.1:8000/recipes/import/{job_id}/preview"
```

### Step 4: Commit to recipe DB

```bash
curl -X POST "http://127.0.0.1:8000/recipes/import/{job_id}/commit"
```

## OpenClaw Integration Guide

You can connect OpenClaw to this service using OpenAPI import (best) or manual HTTP actions.

### Option A (Recommended): OpenAPI import

1. Start backend locally:

```bash
uvicorn main:app --reload
```

2. In OpenClaw, add a new API tool/integration.
3. Set base URL:

```text
http://127.0.0.1:8000
```

4. Set OpenAPI schema URL:

```text
http://127.0.0.1:8000/openapi.json
```

5. Import endpoints and expose at least:
   - `POST /menu/generate`
   - `POST /recipes`
   - `GET /recipes`
   - `PUT /recipes/{recipe_id}`
   - `DELETE /recipes/{recipe_id}`
   - `POST /recipes/search/hybrid`
   - Import flow endpoints under `/recipes/import/*`

### Option B: Manual action mapping

If your OpenClaw instance does not support OpenAPI import, create HTTP actions manually:

- Action: `generate_menu`
  - Method: `POST`
  - URL: `http://127.0.0.1:8000/menu/generate`
  - Body JSON: `people_count`, `dish_count`, `preferences`, `available_ingredients`, `constraints`

- Action: `create_recipe`
  - Method: `POST`
  - URL: `http://127.0.0.1:8000/recipes`
  - Body JSON: full recipe structure

- Action: `search_recipe`
  - Method: `POST`
  - URL: `http://127.0.0.1:8000/recipes/search/hybrid`

- Action group: `import_xiachufang`
  - `POST /recipes/import`
  - `GET /recipes/import/{job_id}`
  - `POST /recipes/import/{job_id}/resume-with-cookies`
  - `POST /recipes/import/{job_id}/submit-html`
  - `GET /recipes/import/{job_id}/preview`
  - `POST /recipes/import/{job_id}/commit`

### OpenClaw workflow suggestion for Xiachufang

Use this orchestration in OpenClaw:

1. Call `POST /recipes/import` with URL.
2. If status is `ready_to_commit`: call preview then commit.
3. If status is `challenge_required`:
   - Ask user to finish browser verification.
   - Ask user to paste cookie string.
   - Call `/resume-with-cookies`.
4. If still not ready:
   - Ask user to paste full page HTML.
   - Call `/submit-html`.
5. Call `/preview`, let user confirm.
6. Call `/commit`.

This gives stable behavior even when anti-bot checks are active.

## Notes

- SQLite migrations are lightweight and handled at startup for current schema additions.
- Seed data is auto-inserted on first run if no recipes exist.
- No authentication is included in this MVP.
