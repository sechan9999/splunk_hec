from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError:
    from sqlalchemy.orm import declarative_base
    DeclarativeBase = declarative_base()  # type: ignore[assignment,misc]

from app.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


if isinstance(DeclarativeBase, type) and hasattr(DeclarativeBase, "metadata"):
    class Base(DeclarativeBase):
        pass
else:
    Base = DeclarativeBase  # type: ignore[misc,assignment]


def init_db() -> None:
    from app.domain import models  # noqa: F401 — register mappers

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
