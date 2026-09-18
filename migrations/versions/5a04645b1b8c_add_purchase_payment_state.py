"""add purchase payment state

Revision ID: 5a04645b1b8c
Revises: b8c9d0e1f2a3
Create Date: 2026-09-18 16:30:15.974311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5a04645b1b8c'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        status_enum = postgresql.ENUM('PENDING', 'SUCCESS', 'FAILED', name='purchase_status_enum')
        status_enum.create(conn, checkfirst=True)
        
    status_col_type = sa.Enum('PENDING', 'SUCCESS', 'FAILED', name='purchase_status_enum')
    
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', status_col_type, server_default='PENDING', nullable=False))
        batch_op.add_column(sa.Column('provider_transaction_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.drop_column('paid_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('provider_transaction_id')
        batch_op.drop_column('status')
        
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        status_enum = postgresql.ENUM('PENDING', 'SUCCESS', 'FAILED', name='purchase_status_enum')
        status_enum.drop(conn, checkfirst=True)
