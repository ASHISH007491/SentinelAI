"""add user role

Revision ID: b0a5b847fd70
Revises: 65aed1f4b0cb
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b0a5b847fd70'
down_revision: Union[str, None] = '65aed1f4b0cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values must match app.models.user.Role
_role_enum = sa.Enum("ADMINISTRATOR", "ANALYST", "DEVELOPER", "VIEWER", name="role")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("role", _role_enum, nullable=False, server_default="ANALYST")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("role")
