"""Create minimal movies table for FK compatibility

Revision ID: 07d7402c461b
Revises: 9db5463cefb0
Create Date: 2025-06-09 08:02:16.194353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07d7402c461b'
down_revision: Union[str, None] = '9db5463cefb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create minimal movies table to support FK from cart_items
    # This will be replaced with full movies table when movies functionality is implemented
    op.create_table('movies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, comment='Temporary field'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        comment='Minimal movies table for FK compatibility. Will be replaced with full implementation.'
    )
    
    # Now add the FK constraint from cart_items to movies
    op.create_foreign_key(
        'fk_cart_items_movie_id_movies', 
        'cart_items', 
        'movies', 
        ['movie_id'], 
        ['id'], 
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Remove FK constraint first
    op.drop_constraint('fk_cart_items_movie_id_movies', 'cart_items', type_='foreignkey')
    
    # Drop movies table
    op.drop_table('movies') 