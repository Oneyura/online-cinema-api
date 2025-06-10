"""Add default user groups

Revision ID: ca9e4ca00506
Revises: 3059e38cc136
Create Date: 2025-06-10 09:42:57.716918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = 'ca9e4ca00506'
down_revision: Union[str, None] = '3059e38cc136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Define user_groups table structure for data operations
    user_groups_table = table(
        'user_groups',
        column('id', sa.Integer),
        column('name', sa.Enum('USER', 'MODERATOR', 'ADMIN', name='usergroupenum'))
    )
    
    # Insert default user groups
    op.bulk_insert(
        user_groups_table,
        [
            {'id': 1, 'name': 'USER'},
            {'id': 2, 'name': 'MODERATOR'},
            {'id': 3, 'name': 'ADMIN'},
        ]
    )


def downgrade() -> None:
    # Remove default user groups (in reverse order due to potential FK constraints)
    op.execute("DELETE FROM user_groups WHERE name IN ('USER', 'MODERATOR', 'ADMIN')") 