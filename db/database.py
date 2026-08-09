"""
Punto único de conexión a la base de datos.

Uso típico:
    from db.database import get_session, init_db

    init_db()  # crea las tablas si no existen
    with get_session() as session:
        session.add(...)
        session.commit()
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from db.models import Base

# check_same_thread solo aplica a SQLite; en Postgres se ignora sin problema
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"connect_timeout": 15}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """Crea todas las tablas definidas en models.py si no existen todavía."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()