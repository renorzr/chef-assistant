"""baseline schema

Revision ID: 20260419_000001
Revises:
Create Date: 2026-04-19 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

from models import Base


# revision identifiers, used by Alembic.
revision = "20260419_000001"
down_revision = None
branch_labels = None
depends_on = None


def _create_missing_tables() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    _create_missing_tables()

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "recipes" in tables:
        recipe_cols = _column_names(inspector, "recipes")
        if "cover_image_url" not in recipe_cols:
            op.add_column("recipes", sa.Column("cover_image_url", sa.String(length=1000), nullable=True))

    if "recipe_steps" in tables:
        step_cols = _column_names(inspector, "recipe_steps")
        if "image_url" not in step_cols:
            op.add_column("recipe_steps", sa.Column("image_url", sa.String(length=1000), nullable=True))

    if "meal_plans" in tables:
        meal_plan_cols = _column_names(inspector, "meal_plans")
        if "expected_finish_at" not in meal_plan_cols:
            op.add_column("meal_plans", sa.Column("expected_finish_at", sa.DateTime(timezone=True), nullable=True))
            if bind.dialect.name == "sqlite":
                bind.execute(text("UPDATE meal_plans SET expected_finish_at = datetime(created_at, '+24 hours') WHERE expected_finish_at IS NULL"))
            else:
                bind.execute(text("UPDATE meal_plans SET expected_finish_at = created_at + INTERVAL '24 hours' WHERE expected_finish_at IS NULL"))
        if "cancelled_at" not in meal_plan_cols:
            op.add_column("meal_plans", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    if "recipe_ingredients" in tables:
        recipe_ing_cols = _column_names(inspector, "recipe_ingredients")
        if "note" not in recipe_ing_cols:
            op.add_column("recipe_ingredients", sa.Column("note", sa.Text(), nullable=True))
        if "optional" not in recipe_ing_cols:
            op.add_column(
                "recipe_ingredients",
                sa.Column("optional", sa.Integer(), nullable=False, server_default="0"),
            )

    inspector = inspect(bind)

    if "recipes" in tables:
        recipe_indexes = _index_names(inspector, "recipes")
        if "ix_recipes_name" not in recipe_indexes:
            op.create_index("ix_recipes_name", "recipes", ["name"], unique=False)

    if "ingredients" in tables:
        ingredient_indexes = _index_names(inspector, "ingredients")
        if "ix_ingredients_name" not in ingredient_indexes:
            op.create_index("ix_ingredients_name", "ingredients", ["name"], unique=True)

    if "recipe_embeddings" in tables:
        embedding_indexes = _index_names(inspector, "recipe_embeddings")
        if "ix_recipe_embeddings_recipe_id" not in embedding_indexes:
            op.create_index("ix_recipe_embeddings_recipe_id", "recipe_embeddings", ["recipe_id"], unique=True)

    if "chat_sessions" in tables:
        session_indexes = _index_names(inspector, "chat_sessions")
        if "ix_chat_sessions_session_id" not in session_indexes:
            op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"], unique=True)

    if "chat_messages" in tables:
        message_indexes = _index_names(inspector, "chat_messages")
        if "ix_chat_messages_session_ref_id" not in message_indexes:
            op.create_index("ix_chat_messages_session_ref_id", "chat_messages", ["session_ref_id"], unique=False)

    if "menus" in tables:
        menu_indexes = _index_names(inspector, "menus")
        if "ix_menus_name" not in menu_indexes:
            op.create_index("ix_menus_name", "menus", ["name"], unique=False)

    if "menu_categories" in tables:
        category_indexes = _index_names(inspector, "menu_categories")
        if "ix_menu_categories_menu_id" not in category_indexes:
            op.create_index("ix_menu_categories_menu_id", "menu_categories", ["menu_id"], unique=False)

    if "menu_items" in tables:
        menu_item_indexes = _index_names(inspector, "menu_items")
        if "ix_menu_items_menu_id" not in menu_item_indexes:
            op.create_index("ix_menu_items_menu_id", "menu_items", ["menu_id"], unique=False)
        if "ix_menu_items_recipe_id" not in menu_item_indexes:
            op.create_index("ix_menu_items_recipe_id", "menu_items", ["recipe_id"], unique=False)

    if "meal_plans" in tables:
        meal_plan_indexes = _index_names(inspector, "meal_plans")
        if "ix_meal_plans_name" not in meal_plan_indexes:
            op.create_index("ix_meal_plans_name", "meal_plans", ["name"], unique=False)
        if "ix_meal_plans_status" not in meal_plan_indexes:
            op.create_index("ix_meal_plans_status", "meal_plans", ["status"], unique=False)

    if "meal_plan_items" in tables:
        meal_plan_item_indexes = _index_names(inspector, "meal_plan_items")
        if "ix_meal_plan_items_meal_plan_id" not in meal_plan_item_indexes:
            op.create_index("ix_meal_plan_items_meal_plan_id", "meal_plan_items", ["meal_plan_id"], unique=False)
        if "ix_meal_plan_items_recipe_id" not in meal_plan_item_indexes:
            op.create_index("ix_meal_plan_items_recipe_id", "meal_plan_items", ["recipe_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for baseline schema migration.")
