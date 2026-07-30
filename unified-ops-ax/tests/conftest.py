import os
import tempfile

# Configure an isolated, offline environment BEFORE app modules import config.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["DEFAULT_LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["VECTOR_BACKEND"] = "memory"

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.rag.vectorstore import get_vector_store  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.drop_all(bind=engine)
    init_db()
    get_vector_store().clear()
    yield


@pytest.fixture
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
