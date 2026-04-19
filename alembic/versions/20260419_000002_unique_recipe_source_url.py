"""add unique index for recipe source_url

Revision ID: 20260419_000002
Revises: 20260419_000001
Create Date: 2026-04-19 00:00:02
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260419_000002"
down_revision = "20260419_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "recipes" not in tables:
        return

    index_names = {index["name"] for index in inspector.get_indexes("recipes")}
    if "ix_recipes_source_url" not in index_names:
        op.create_index("ix_recipes_source_url", "recipes", ["source_url"], unique=True)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for this migration.")
