"""Placeholder: DB may already reference this revision (e.g. local branch).

Revision ID: 0002_add_chat_messages
Revises: 0001_baseline
Create Date: 2026-05-13

If this migration was never applied on your database, upgrade() is a no-op.
If your DB was stamped or migrated with this id elsewhere, keep this file so
`alembic upgrade head` can resolve the revision graph.
"""

from alembic import op

revision = "0002_add_chat_messages"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
