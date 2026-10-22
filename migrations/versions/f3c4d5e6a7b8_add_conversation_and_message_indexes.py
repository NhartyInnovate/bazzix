"""add conversation and message indexes

Revision ID: f3c4d5e6a7b8
Revises: e1a2b3c4d5e6
Create Date: 2026-10-22 11:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c4d5e6a7b8'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add covering indexes for conversation listing and message history."""
    op.create_index(
        'ix_conversations_user_pinned_updated',
        'conversations',
        ['user_id', sa.text('is_pinned DESC'), sa.text('updated_at DESC'), sa.text('id DESC')],
        unique=False,
    )
    op.create_index(
        'ix_messages_conversation_id_created_at',
        'messages',
        ['conversation_id', sa.text('created_at ASC'), sa.text('id ASC')],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: drop covering indexes."""
    op.drop_index('ix_messages_conversation_id_created_at', table_name='messages')
    op.drop_index('ix_conversations_user_pinned_updated', table_name='conversations')
