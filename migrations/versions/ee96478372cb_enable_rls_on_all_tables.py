"""enable_rls_on_all_tables

Revision ID: ee96478372cb
Revises: 5a04645b1b8c
Create Date: 2026-09-22 20:34:47.632938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee96478372cb'
down_revision: Union[str, Sequence[str], None] = '5a04645b1b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tables = [
    "users",
    "wallets",
    "subscriptions",
    "purchases",
    "ledger_transactions",
    "conversations",
    "messages",
    "ai_request_logs"
]

def upgrade() -> None:
    for table in tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in tables:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
