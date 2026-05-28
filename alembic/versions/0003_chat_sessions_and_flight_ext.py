"""채팅 세션·메시지 테이블, flights 확장 (api_sync_status, share_token), pg_trgm 확장

Revision ID: 0003_flight_ext
Revises: 0002_auth_refresh_email
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_flight_ext"
down_revision = "0002_auth_refresh_email"
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


def _unique_constraint_exists(bind, table_name: str, constraint_name: str) -> bool:
    return any(
        uc["name"] == constraint_name for uc in inspect(bind).get_unique_constraints(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()

    # pg_trgm: 하이브리드 키워드 검색 성능 보조
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    if not _table_exists(bind, "chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("session_id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.user_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column(
                "terminal", sa.String(10), nullable=False, server_default=sa.text("'T1'")
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    if not _table_exists(bind, "chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("message_id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column(
                "session_id",
                sa.String(36),
                sa.ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("mode", sa.String(20), nullable=True),
            sa.Column("sources", sa.JSON(), nullable=True),
            sa.Column("feedback", sa.String(20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    if not _column_exists(bind, "flights", "api_sync_status"):
        op.add_column(
            "flights",
            sa.Column("api_sync_status", sa.String(20), nullable=True),
        )

    # airport_documents: 증분 크롤용 content_hash
    if not _column_exists(bind, "airport_documents", "content_hash"):
        op.add_column(
            "airport_documents",
            sa.Column("content_hash", sa.String(64), nullable=True),
        )
    if not _index_exists(bind, "airport_documents", "ix_airport_documents_content_hash"):
        op.create_index(
            "ix_airport_documents_content_hash",
            "airport_documents",
            ["content_hash"],
        )

    if not _column_exists(bind, "flights", "share_token"):
        op.add_column(
            "flights",
            sa.Column("share_token", sa.String(64), nullable=True),
        )
    if not _unique_constraint_exists(bind, "flights", "uq_flights_share_token"):
        op.create_unique_constraint("uq_flights_share_token", "flights", ["share_token"])
    if not _index_exists(bind, "flights", "ix_flights_share_token"):
        op.create_index("ix_flights_share_token", "flights", ["share_token"])


def downgrade() -> None:
    op.drop_index("ix_airport_documents_content_hash", table_name="airport_documents")
    op.drop_column("airport_documents", "content_hash")
    op.drop_index("ix_flights_share_token", table_name="flights")
    op.drop_constraint("uq_flights_share_token", "flights", type_="unique")
    op.drop_column("flights", "share_token")
    op.drop_column("flights", "api_sync_status")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
