"""
SQLAlchemy async models for the demo deliverable.

Three tables:
  - audit_events    : mirrors the JSONL audit schema (src/audit/logger.py) plus
                      identity (user_sub/user_name) and demo display fields so the
                      admin drawer can show the sanitized prompt, intercepted output,
                      block reason, and safe-version suggestion.
  - conversations   : a chat thread owned by a user.
  - messages        : individual turns in a conversation (role/content/blocked flag).

The proxy writes audit_events (best-effort). The webui writes conversations/messages.
"""
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    app_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(16), index=True)          # ALLOWED | BLOCKED | ERROR
    block_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    findings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    redaction_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Identity (from X-User-Identity header set by webui_api)
    user_sub: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Demo display fields (nullable; populated when available)
    sanitized_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_sub: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(256), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))                # user | assistant | notice
    content: Mapped[str] = mapped_column(Text)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
