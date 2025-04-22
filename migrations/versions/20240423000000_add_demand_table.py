"""add_demand_table

Revision ID: 20240423000000
Revises: 20240325152900
Create Date: 2024-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240423000000'
down_revision = '20240325152900'
branch_labels = None
depends_on = None


def upgrade():
    # Create demand_data table
    op.create_table('demand_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('datetime', sa.DateTime(), nullable=False),
        sa.Column('consumption', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('datetime')
    )


def downgrade():
    # Drop demand_data table
    op.drop_table('demand_data') 