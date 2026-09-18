"""add_bazzix_credit_products_phase_2c

Revision ID: b8c9d0e1f2a3
Revises: b0d80f7e5795
Create Date: 2026-09-18 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'b0d80f7e5795'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'SUBSCRIPTION_ALLOCATION'")
            op.execute("ALTER TYPE transaction_type_enum ADD VALUE IF NOT EXISTS 'EXPIRY'")

    with op.batch_alter_table('ledger_transactions', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_ledger_tx_ref', ['transaction_type', 'reference_id'])

    op.create_table('purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.String(), nullable=False),
        sa.Column('product_name_snapshot', sa.String(), nullable=False),
        sa.Column('price_amount', sa.Integer(), nullable=False),
        sa.Column('price_currency', sa.String(), nullable=False),
        sa.Column('credit_allocation', sa.Integer(), nullable=False),
        sa.Column('payment_provider', sa.String(), nullable=False),
        sa.Column('payment_reference', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_provider', 'payment_reference', name='uq_payment_provider_ref')
    )
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_purchases_user_id'), ['user_id'], unique=False)

    op.create_table('subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'PAST_DUE', 'CANCELED', name='subscription_status_enum'), nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_subscriptions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(
            'ix_active_subscription',
            ['user_id'],
            unique=True,
            postgresql_where=sa.text("status = 'ACTIVE'"),
            sqlite_where=sa.text("status = 'ACTIVE'")
        )


def downgrade():
    with op.batch_alter_table('subscriptions', schema=None) as batch_op:
        batch_op.drop_index('ix_active_subscription', postgresql_where=sa.text("status = 'ACTIVE'"), sqlite_where=sa.text("status = 'ACTIVE'"))
        batch_op.drop_index(batch_op.f('ix_subscriptions_user_id'))
    op.drop_table('subscriptions')

    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_purchases_user_id'))
    op.drop_table('purchases')

    with op.batch_alter_table('ledger_transactions', schema=None) as batch_op:
        batch_op.drop_constraint('uq_ledger_tx_ref', type_='unique')
