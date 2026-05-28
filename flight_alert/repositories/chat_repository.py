# flight_alert/repositories/chat_repository.py
"""채팅 세션 및 메시지 CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flight_alert.models.chat_session import ChatMessage, ChatSession


class ChatRepository:
    async def create_session(
        self,
        db: AsyncSession,
        user_id: int,
        terminal: str = "T1",
        title: str | None = None,
    ) -> ChatSession:
        new_session = ChatSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            terminal=terminal,
            title=title,
        )
        db.add(new_session)
        await db.flush()
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.session_id == new_session.session_id)
            .options(selectinload(ChatSession.messages))
        )
        return result.scalar_one()

    async def get_session(
        self, db: AsyncSession, session_id: str, user_id: int
    ) -> ChatSession | None:
        result = await db.execute(
            select(ChatSession)
            .where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
            .options(selectinload(ChatSession.messages))
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self, db: AsyncSession, user_id: int, limit: int = 20
    ) -> list[ChatSession]:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_session(
        self, db: AsyncSession, session_id: str, user_id: int
    ) -> bool:
        session = await db.scalar(
            select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        if not session:
            return False
        await db.delete(session)
        return True

    async def add_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        mode: str | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            mode=mode,
            sources=sources,
        )
        db.add(msg)
        # updated_at 갱신
        await db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await db.flush()
        await db.refresh(msg)
        return msg

    async def update_session_title(
        self, db: AsyncSession, session_id: str, title: str
    ) -> None:
        await db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(title=title, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )

    async def set_feedback(
        self,
        db: AsyncSession,
        message_id: int,
        session_id: str,
        user_id: int,
        feedback: str,
    ) -> ChatMessage | None:
        msg = await db.scalar(
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_id == ChatSession.session_id)
            .where(
                ChatMessage.message_id == message_id,
                ChatMessage.session_id == session_id,
                ChatSession.user_id == user_id,
                ChatMessage.role == "assistant",
            )
        )
        if not msg:
            return None
        msg.feedback = feedback
        await db.flush()
        return msg


chat_repository = ChatRepository()
