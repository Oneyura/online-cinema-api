"""Merge heads

Revision ID: 4372c30c375f
Revises: 0125de09dcf9, ca9e4ca00506
Create Date: 2025-06-11 17:27:40.035579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4372c30c375f'
down_revision: Union[str, None] = ('0125de09dcf9', 'ca9e4ca00506')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass 