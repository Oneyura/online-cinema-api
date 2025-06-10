"""add_pending_payment_status

Revision ID: 0125de09dcf9
Revises: 3059e38cc136
Create Date: 2025-06-10 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0125de09dcf9'
down_revision: Union[str, None] = '3059e38cc136'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add PENDING value to PaymentStatus enum
    op.execute("ALTER TYPE paymentstatus ADD VALUE 'PENDING'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type
    pass 