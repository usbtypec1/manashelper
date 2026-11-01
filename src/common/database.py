"""One SQLAlchemy registry shared by all application-owned models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
