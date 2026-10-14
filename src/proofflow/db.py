"""Database connection and session factory."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql+psycopg://user:password@localhost:5433/proofflow"
    )


def make_engine(url: str | None = None):
    return create_engine(url or database_url())


def make_session_factory(url: str | None = None):
    return sessionmaker(make_engine(url), expire_on_commit=False)
