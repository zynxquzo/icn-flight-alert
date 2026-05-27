"""chat_messages.user_id 컬럼 제거 (session_id → chat_sessions → user_id 로 연결)

Revision ID: 0006_drop_chat_messages_user_id
Revises: 0005_fix_chat_role_varchar
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_drop_chat_messages_user_id"
down_revision = "0005_fix_chat_role_varchar"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    if not inspect(bind).has_table(table_name):
        return False
    return any(c["name"] == column_name for c in inspect(bind).get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "chat_messages", "user_id"):
        op.drop_column("chat_messages", "user_id")


def downgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "chat_messages", "user_id"):
        op.add_column(
            "chat_messages",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )
