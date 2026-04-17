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
  - Reusable menu CRUD: `/menus/*`
  - Generate reusable menu from natural language: `POST /menus/generate-from-text`
- Search
  - Vector search: `POST /recipes/search/vector`
  - Hybrid search (keyword + vector rerank): `POST /recipes/search/hybrid`
  - Reindex embeddings: `POST /admin/embeddings/reindex`
  - Audit status: `GET /admin/embeddings/audit`
  - Repair missing embeddings: `POST /admin/embeddings/repair-missing`
- Import from link (Xiachufang)
  - Import recipe pages from App-provided HTML
  - LLM-based recipe parsing with fallback parser

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

### 2.1) Run frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

Notes:
- Frontend chat page calls a mocked `POST /chat/messages` flow for now.
- Frontend API calls use `/api/*` and are proxied by Vite to backend `http://127.0.0.1:8000`.

### 2.2) Run with Docker

Build and run the single application container:

```bash
docker compose up --build
```

This serves both backend and built frontend from the same container at:

- App: `http://127.0.0.1:8000`

If you also want Docker Compose to start PostgreSQL, use the `with-db` profile:

```bash
docker compose --profile with-db up --build
```

When using the Compose-managed PostgreSQL service, set `DATABASE_URL` in `.env` to something like:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/chef_assistant
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

- Embedding provider (`.env` recommended)
  - This project supports OpenAI-compatible embedding APIs (such as `ofox.ai`).
  - Create `.env` from `.env.example` and fill values:

```bash
cp .env.example .env
```

```env
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://api.ofox.ai/v1
EMBEDDING_API_KEY=your_ofox_api_key
EMBEDDING_MODEL=your_embedding_model_name
EMBEDDING_TIMEOUT_SECONDS=20

EMBEDDING_AUDIT_ENABLED=true
EMBEDDING_AUDIT_INTERVAL_SECONDS=600
EMBEDDING_AUDIT_BATCH_SIZE=50
EMBEDDING_AUDIT_INITIAL_DELAY_SECONDS=10

RECIPE_PARSER_PROVIDER=openai_compatible
RECIPE_PARSER_BASE_URL=https://api.ofox.ai/v1
RECIPE_PARSER_API_KEY=your_ofox_api_key
RECIPE_PARSER_MODEL=your_parser_model_name
RECIPE_PARSER_TIMEOUT_SECONDS=30

CHAT_LLM_BASE_URL=https://api.ofox.ai/v1
CHAT_LLM_API_KEY=your_ofox_api_key
CHAT_LLM_MODEL=your_chat_model_name
CHAT_LLM_TIMEOUT_SECONDS=30
```

- Strict behavior for vector/hybrid search
  - If embedding service is unavailable or misconfigured, `POST /recipes/search/vector` and `POST /recipes/search/hybrid` return HTTP `503`.
  - This is intentional (no silent fallback), so integration issues are visible early.

- Async embedding on recipe creation
  - `POST /recipes` and `PUT /recipes/{id}` return as soon as recipe data is stored.
  - Embedding generation runs in a background task.
  - The periodic audit loop also repairs any missing embeddings.

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

### Create reusable menu from natural language

```bash
curl -X POST "http://127.0.0.1:8000/menus/generate-from-text" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "工作日晚餐菜单",
    "preference_text": "想要清淡一点，最好有一道汤，做法简单，4道菜",
    "dish_count": 4
  }'
```

### Menu template CRUD

- `POST /menus`
- `GET /menus`
- `GET /menus/{menu_id}`
- `PUT /menus/{menu_id}`
- `DELETE /menus/{menu_id}`
- `POST /menus/{menu_id}/categories`
- `GET /menus/{menu_id}/categories`
- `PUT /menus/{menu_id}/categories/{category_id}`
- `DELETE /menus/{menu_id}/categories/{category_id}`
- `POST /menus/{menu_id}/items`
- `GET /menus/{menu_id}/items`
- `PUT /menus/{menu_id}/items/{item_id}`
- `DELETE /menus/{menu_id}/items/{item_id}`

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

### Reindex embeddings

Use this after changing embedding provider/model, or when importing old data.

```bash
curl -X POST "http://127.0.0.1:8000/admin/embeddings/reindex" \
  -H "Content-Type: application/json" \
  -d '{
    "only_missing": false
  }'
```

### Embedding audit status

```bash
curl "http://127.0.0.1:8000/admin/embeddings/audit"
```

### Repair missing embeddings (manual trigger)

```bash
curl -X POST "http://127.0.0.1:8000/admin/embeddings/repair-missing" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 50
  }'
```

## Xiachufang Import From HTML

The backend no longer fetches Xiachufang pages directly. In the recommended architecture, your App opens the Xiachufang page, the user completes any verification there, then the App submits the final page HTML to this backend.

### Import one or more recipe pages from HTML

```bash
curl -X POST "http://127.0.0.1:8000/recipes/import/from-html" \
  -H "Content-Type: application/json" \
  -d '{
    "recipes": [
      {
        "source_url": "https://www.xiachufang.com/recipe/107377415/",
        "html": "<html>...</html>"
      }
    ]
  }'
```

Import parsing behavior:
- Primary parser: LLM extraction (OpenAI-compatible endpoint)
- Fallback parser: rule-based extraction if LLM parser fails
- Ingredient list parsing: batch LLM parsing per recipe, with note/optional preservation

## OpenClaw Integration Guide

You can connect OpenClaw to this service using OpenAPI import (best) or manual HTTP actions.

### Skill JSON install (recommended)

Prebuilt skill file is provided: `chef_assistant.skill.json`

1. Start backend: `uvicorn main:app --reload`
2. In OpenClaw, choose import skill from JSON file
3. Select `chef_assistant.skill.json`
4. Run quick checks: `list_recipes`, `generate_menu`, `search_hybrid`

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
   - `POST /recipes/import/from-html`

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
  - `POST /recipes/import/from-html`

### OpenClaw workflow suggestion for Xiachufang

Use this orchestration in OpenClaw:

1. Let the App open Xiachufang inside its own WebView.
2. After verification, let the App read final page HTML.
3. Call `POST /recipes/import/from-html` with one or more recipe pages.

## Notes

- SQLite migrations are lightweight and handled at startup for current schema additions.
- Seed data is auto-inserted on first run if no recipes exist.
- No authentication is included in this MVP.
