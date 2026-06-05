"""
History routes — persisted chat conversations per user.

  GET    /api/history                 : list the current user's conversations
  POST   /api/history                 : create a new conversation
  GET    /api/history/{id}            : get one conversation with its messages
  POST   /api/history/{id}/messages   : append a message (role/content/blocked/block_code)
  DELETE /api/history/{id}            : delete a conversation

All scoped to the authenticated user (user_sub from the JWT).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from ..deps import require_user
from src.db.session import get_session_factory
from src.db.models import Conversation, Message

router = APIRouter(prefix="/api/history", tags=["history"])


class NewConversation(BaseModel):
    title: Optional[str] = "New chat"


class NewMessage(BaseModel):
    role: str
    content: str
    blocked: bool = False
    block_code: Optional[str] = None


def _conv_summary(c: Conversation) -> dict:
    return {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()}


def _msg(m: Message) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content,
            "blocked": m.blocked, "block_code": m.block_code,
            "created_at": m.created_at.isoformat()}


@router.get("")
async def list_conversations(user: dict = Depends(require_user)):
    factory = get_session_factory()
    try:
        async with factory() as session:
            q = (select(Conversation)
                 .where(Conversation.user_sub == user["sub"])
                 .order_by(Conversation.updated_at.desc()))
            rows = (await session.execute(q)).scalars().all()
            return {"conversations": [_conv_summary(c) for c in rows]}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")


@router.post("")
async def create_conversation(body: NewConversation, user: dict = Depends(require_user)):
    factory = get_session_factory()
    try:
        async with factory() as session:
            conv = Conversation(user_sub=user["sub"], title=body.title or "New chat")
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            return _conv_summary(conv)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")


@router.get("/{conv_id}")
async def get_conversation(conv_id: int, user: dict = Depends(require_user)):
    factory = get_session_factory()
    try:
        async with factory() as session:
            q = (select(Conversation)
                 .where(Conversation.id == conv_id, Conversation.user_sub == user["sub"])
                 .options(selectinload(Conversation.messages)))
            conv = (await session.execute(q)).scalar_one_or_none()
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            return {**_conv_summary(conv), "messages": [_msg(m) for m in conv.messages]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")


@router.post("/{conv_id}/messages")
async def add_message(conv_id: int, body: NewMessage, user: dict = Depends(require_user)):
    factory = get_session_factory()
    try:
        async with factory() as session:
            q = select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_sub == user["sub"])
            conv = (await session.execute(q)).scalar_one_or_none()
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            msg = Message(conversation_id=conv_id, role=body.role, content=body.content,
                          blocked=body.blocked, block_code=body.block_code)
            session.add(msg)
            # Title the conversation from the first user message
            if conv.title == "New chat" and body.role == "user":
                conv.title = body.content[:48] + ("…" if len(body.content) > 48 else "")
            await session.commit()
            await session.refresh(msg)
            return _msg(msg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: int, user: dict = Depends(require_user)):
    factory = get_session_factory()
    try:
        async with factory() as session:
            q = select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_sub == user["sub"])
            conv = (await session.execute(q)).scalar_one_or_none()
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found.")
            await session.delete(conv)
            await session.commit()
            return {"deleted": conv_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
