import datetime
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    DECIMAL,
    Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional

from src.database.models.movies import MovieModel
from src.database.models.base import Base


class UserModel(Base):
    pass


class UserRole(Base):
    pass
