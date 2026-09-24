"""add admin role and audit log

Revision ID: 5a22fe847666
Revises: ee96478372cb
Create Date: 2026-09-24 13:42:46.283903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a22fe847666'
down_revision: Union[str, Sequence[str], None] = 'ee96478372cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create RoleType enum
    role_type_enum = sa.Enum('USER', 'ADMIN', name='role_type_enum')
    role_type_enum.create(op.get_bind())

    # Add role column to users with default 'USER'
    op.add_column('users', sa.Column('role', role_type_enum, nullable=False, server_default='USER'))

    # Create admin_audit_logs table
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_user_id', sa.Integer(), nullable=False),
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        sa.Column('target_user_email', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_logs_id'), 'admin_audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_admin_audit_logs_admin_user_id'), 'admin_audit_logs', ['admin_user_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_logs_target_user_id'), 'admin_audit_logs', ['target_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_admin_audit_logs_target_user_id'), table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_admin_user_id'), table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')

    op.drop_column('users', 'role')
    
    role_type_enum = sa.Enum('USER', 'ADMIN', name='role_type_enum')
    role_type_enum.drop(op.get_bind())
