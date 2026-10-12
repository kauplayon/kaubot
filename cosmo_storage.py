"""Persistent storage for Cosmo accounts and synchronized user data."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "cosmo_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    data: Mapped["UserData | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class UserData(Base):
    __tablename__ = "cosmo_user_data"

    user_id: Mapped[int] = mapped_column(ForeignKey("cosmo_users.id", ondelete="CASCADE"), primary_key=True)
    memory: Mapped[str] = mapped_column(Text, default="", nullable=False)
    conversations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    tasks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user: Mapped[User] = relationship(back_populates="data")


_engine = None
_SessionLocal = None
_storage_error: str | None = None


def normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def configure_storage(database_url: str | None = None) -> bool:
    """Configure storage from DATABASE_URL. Never silently use ephemeral disk in production."""
    global _engine, _SessionLocal, _storage_error
    url = normalize_database_url(database_url if database_url is not None else os.getenv("DATABASE_URL", ""))
    if not url:
        _engine = None
        _SessionLocal = None
        _storage_error = "DATABASE_URL não configurada."
        return False
    try:
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=300, future=True)
        Base.metadata.create_all(engine)
        _engine = engine
        _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        _storage_error = None
        return True
    except Exception as exc:
        _engine = None
        _SessionLocal = None
        _storage_error = f"{type(exc).__name__}: não foi possível conectar ao banco."
        return False


def storage_ready() -> bool:
    return _SessionLocal is not None


def storage_error() -> str | None:
    return _storage_error


def session_factory():
    if _SessionLocal is None:
        raise RuntimeError("O armazenamento persistente não está configurado.")
    return _SessionLocal()


def get_or_create_data(db, user: User) -> UserData:
    row = db.get(UserData, user.id)
    if row is None:
        row = UserData(user_id=user.id, memory="", conversations=[], tasks=[], notes=[], preferences={})
        db.add(row)
        db.flush()
    return row


# Initialize only when a persistent DATABASE_URL was supplied. A failed connection
# leaves the app usable in local-only mode and is reported by /health.
configure_storage()
