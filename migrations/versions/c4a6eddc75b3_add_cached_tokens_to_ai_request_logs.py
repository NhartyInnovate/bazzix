"""add_cached_tokens_to_ai_request_logs

Revision ID: c4a6eddc75b3
Revises: a8f754ca7592
Create Date: 2026-09-18 12:54:36.515026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a6eddc75b3'
down_revision: Union[str, Sequence[str], None] = 'a8f754ca7592'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ai_request_logs', sa.Column('cached_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ai_request_logs', 'cached_tokens')
