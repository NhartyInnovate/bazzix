"""add_reservation_release_to_transaction_type

Revision ID: a8f754ca7592
Revises: 78a60373f321
Create Date: 2026-09-18 12:49:04.568004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f754ca7592'
down_revision: Union[str, Sequence[str], None] = '78a60373f321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # We must commit the current transaction because ALTER TYPE ADD VALUE cannot run inside a transaction block in some older Postgres versions.
    # However, modern Postgres allows it if it's the only command. To be safe, we use connection.execute directly.
    op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'RESERVATION_RELEASE'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not natively support dropping a value from an ENUM type.
    # The safest downgrade path is to leave the value in place but unused.
    pass
