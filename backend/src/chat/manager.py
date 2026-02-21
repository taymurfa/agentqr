"""Chat session manager: history, context, session persistence."""

import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ChatSession, Message


class ChatManager:
    """Manages chat sessions and message history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, title: str = "New Research Chat") -> ChatSession:
        session = ChatSession(title=title)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        uid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        stmt = select(ChatSession).where(ChatSession.id == uid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.updated_at.desc().nullslast(), ChatSession.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "title": s.title,
                "created_at": str(s.created_at),
                "updated_at": str(s.updated_at) if s.updated_at else None,
            }
            for s in sessions
        ]

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agents_used: list[str] = None,
        context_sources: list[dict] = None,
        tokens_used: int = 0,
    ) -> Message:
        msg = Message(
            session_id=uuid.UUID(session_id) if isinstance(session_id, str) else session_id,
            role=role,
            content=content,
            agents_used=agents_used,
            context_sources=context_sources,
            tokens_used=tokens_used,
        )
        self.db.add(msg)

        # Update session timestamp
        session = await self.get_session(session_id)
        if session:
            session.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict]:
        uid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        stmt = (
            select(Message)
            .where(Message.session_id == uid)
            .order_by(Message.created_at)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "agents_used": m.agents_used,
                "context_sources": m.context_sources,
                "created_at": str(m.created_at),
            }
            for m in messages
        ]

    async def get_conversation_context(
        self,
        session_id: str,
        max_messages: int = 20,
    ) -> list[dict]:
        """Get recent conversation history formatted for LLM context."""
        messages = await self.get_messages(session_id, limit=max_messages)
        return [{"role": m["role"], "content": m["content"]} for m in messages]
