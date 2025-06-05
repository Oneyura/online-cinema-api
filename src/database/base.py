from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, registry

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create registry with naming convention
mapper_registry = registry(metadata=MetaData(naming_convention=convention))


class Base(DeclarativeBase):
    """Base class for all models."""

    registry = mapper_registry
    metadata = mapper_registry.metadata

    @declared_attr  # type: ignore
    def __tablename__(cls) -> str:
        """Generate table name automatically."""
        return cls.__name__.lower()
