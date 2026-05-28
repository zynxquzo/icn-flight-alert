"""chat_messages를 새 세션 모델에 맞게 정리

Revision ID: 0004_chat_fix
Revises: 0003_flight_ext
Create Date: 2026-05-28
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0004_chat_fix"
down_revision = "0003_flight_ext"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    return inspect(bind).has_table(table_name)


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(col["name"] == column_name for col in inspect(bind).get_columns(table_name))


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(idx["name"] == index_name for idx in inspect(bind).get_indexes(table_name))


def _constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(bind, table_name):
        return False
    return any(
        fk["name"] == constraint_name for fk in inspect(bind).get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "chat_messages"):
        return

    if not _column_exists(bind, "chat_messages", "session_id"):
        op.add_column(
            "chat_messages",
            sa.Column("session_id", sa.String(36), nullable=True),
        )
    if not _column_exists(bind, "chat_messages", "feedback"):
        op.add_column(
            "chat_messages",
            sa.Column("feedback", sa.String(20), nullable=True),
        )

    # 기존 레거시 메시지는 user_id 기준으로 세션 1개에 묶습니다.
    result = bind.execute(text("select distinct user_id from chat_messages order by user_id"))
    user_ids = [row[0] for row in result.fetchall()]

    for user_id in user_ids:
        existing_session_id = bind.execute(
            text("select session_id from chat_sessions where user_id = :user_id limit 1"),
            {"user_id": user_id},
        ).scalar()
        if not existing_session_id:
            first_user_message = bind.execute(
                text(
                    """
                    select content
                    from chat_messages
                    where user_id = :user_id and role = 'user'
                    order by created_at asc, chat_message_id asc
                    limit 1
                    """
                ),
                {"user_id": user_id},
            ).scalar()
            session_id = str(uuid.uuid4())
            title = (first_user_message or "기존 채팅 기록")[:80]
            bind.execute(
                text(
                    """
                    insert into chat_sessions (session_id, user_id, title, terminal)
                    values (:session_id, :user_id, :title, 'T1')
                    """
                ),
                {"session_id": session_id, "user_id": user_id, "title": title},
            )
        else:
            session_id = existing_session_id

        bind.execute(
            text("update chat_messages set session_id = :session_id where user_id = :user_id"),
            {"session_id": session_id, "user_id": user_id},
        )

    if _column_exists(bind, "chat_messages", "chat_message_id") and not _column_exists(
        bind, "chat_messages", "message_id"
    ):
        op.alter_column(
            "chat_messages",
            "chat_message_id",
            new_column_name="message_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    if not _constraint_exists(bind, "chat_messages", "fk_chat_messages_session_id"):
        op.create_foreign_key(
            "fk_chat_messages_session_id",
            "chat_messages",
            "chat_sessions",
            ["session_id"],
            ["session_id"],
            ondelete="CASCADE",
        )

    if not _index_exists(bind, "chat_messages", "ix_chat_messages_session_id"):
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    op.alter_column(
        "chat_messages",
        "session_id",
        existing_type=sa.String(36),
        nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "chat_messages", "ix_chat_messages_session_id"):
        op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    if _constraint_exists(bind, "chat_messages", "fk_chat_messages_session_id"):
        op.drop_constraint(
            "fk_chat_messages_session_id",
            "chat_messages",
            type_="foreignkey",
        )
    if _column_exists(bind, "chat_messages", "message_id"):
        op.alter_column(
            "chat_messages",
            "message_id",
            new_column_name="chat_message_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
    if _column_exists(bind, "chat_messages", "feedback"):
        op.drop_column("chat_messages", "feedback")
    if _column_exists(bind, "chat_messages", "session_id"):
        op.drop_column("chat_messages", "session_id")
