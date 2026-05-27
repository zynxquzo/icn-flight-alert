"""chat_messages.role 컬럼을 chat_message_role ENUM에서 VARCHAR(20)으로 변경

Revision ID: 0005_fix_chat_role_varchar
Revises: 0004_chat_fix
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0005_fix_chat_role_varchar"
down_revision = "0004_chat_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"]: c for c in inspect(bind).get_columns("chat_messages")}
    role_col = cols.get("role")
    if role_col and role_col.get("type").__class__.__name__ != "VARCHAR":
        op.execute(text(
            "ALTER TABLE chat_messages ALTER COLUMN role TYPE VARCHAR(20) USING role::text"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("CREATE TYPE IF NOT EXISTS chat_message_role AS ENUM ('user', 'assistant')"))
    op.execute(text(
        "ALTER TABLE chat_messages ALTER COLUMN role "
        "TYPE chat_message_role USING role::chat_message_role"
    ))
