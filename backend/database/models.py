"""
database/models.py

SQLAlchemy ORM models for CHP.

NOTE: Do NOT define a Python property named 'metadata' on any model class —
it shadows DeclarativeBase.metadata which SQLAlchemy uses to build tables.
JSON helpers are exposed as get_meta() / set_meta() methods instead.
"""
import json
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id         = Column(String, primary_key=True)
    name       = Column(String, nullable=False)
    email      = Column(String, nullable=True)
    avatar     = Column(String, nullable=True)   # initials or URL
    created_at = Column(DateTime, default=datetime.utcnow)

    events  = relationship("Event",        back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    threads = relationship("Thread",       back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    briefs  = relationship("HandoffBrief", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class Event(Base):
    """A single normalised signal from any data source."""
    __tablename__ = "events"

    id          = Column(String, primary_key=True)
    user_id     = Column(String, ForeignKey("users.id"), nullable=False)
    source      = Column(String, nullable=False)   # slack|github|notion|email|calendar|mock
    content     = Column(Text,   nullable=False)
    timestamp   = Column(DateTime, nullable=False)
    url         = Column(String, nullable=True)
    event_meta  = Column(Text, default="{}")       # JSON — source-specific metadata
    event_embed = Column(Text, nullable=True)       # JSON float list — embedding vector
    thread_id   = Column(String, ForeignKey("threads.id"), nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    user   = relationship("User",   back_populates="events", lazy="selectin")
    thread = relationship("Thread", back_populates="events", lazy="selectin")

    #  JSON helpers (intentionally NOT named 'metadata') 
    def get_meta(self) -> dict:
        return json.loads(self.event_meta or "{}")

    def set_meta(self, value: dict) -> None:
        self.event_meta = json.dumps(value)

    def get_embedding(self) -> list[float] | None:
        return json.loads(self.event_embed) if self.event_embed else None

    def set_embedding(self, value: list[float] | None) -> None:
        self.event_embed = json.dumps(value) if value is not None else None


class Thread(Base):
    """A semantically-clustered work thread."""
    __tablename__ = "threads"

    id              = Column(String,  primary_key=True)
    user_id         = Column(String,  ForeignKey("users.id"), nullable=False)
    title           = Column(String,  nullable=False)
    description     = Column(Text,    nullable=True)
    status          = Column(String,  default="in_flight")   # in_flight|blocked|done|stale
    staleness_score = Column(Float,   default=0.5)
    confidence      = Column(Float,   default=0.75)
    inferred_count  = Column(Integer, default=0)
    blocker         = Column(Text,    nullable=True)
    next_action     = Column(Text,    nullable=True)
    last_activity   = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user   = relationship("User",  back_populates="threads", lazy="selectin")
    events = relationship("Event", back_populates="thread",  lazy="selectin")


class HandoffBrief(Base):
    """A generated handoff document for a user."""
    __tablename__ = "handoff_briefs"

    id           = Column(String,  primary_key=True)
    user_id      = Column(String,  ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    summary      = Column(Text,    nullable=True)
    brief_data   = Column(Text,    default="[]")   # JSON list of thread summaries
    verified     = Column(Boolean, default=False)
    llm_model    = Column(String,  nullable=True)

    user = relationship("User", back_populates="briefs", lazy="selectin")

    def get_content(self) -> list:
        return json.loads(self.brief_data or "[]")

    def set_content(self, value: list) -> None:
        self.brief_data = json.dumps(value)

    # Convenience property that doesn't collide with SQLAlchemy internals
    @property
    def content(self) -> list:
        return self.get_content()

    @content.setter
    def content(self, value: list) -> None:
        self.set_content(value)
