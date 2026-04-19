"""add recipe created_at

Revision ID: 20260419_000003
Revises: 20260419_000002
Create Date: 2026-04-19 00:00:03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20260419_000003"
down_revision = "20260419_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    recipe_columns = {column["name"] for column in inspector.get_columns("recipes")}

    if "created_at" not in recipe_columns:
        op.add_column("recipes", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        if bind.dialect.name == "sqlite":
            bind.execute(text("UPDATE recipes SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        else:
            bind.execute(text("UPDATE recipes SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for recipe created_at migration.")
