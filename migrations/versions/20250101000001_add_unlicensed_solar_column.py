"""add unlicensed solar column to production data

Revision ID: 20250101000001
Revises: 20250101000000
Create Date: 2025-01-01 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250101000001'
down_revision = '20250101000000'
branch_labels = None
depends_on = None


def upgrade():
    # Add unlicensed_solar column to production_data table
    op.add_column('production_data', sa.Column('unlicensed_solar', sa.Float(), nullable=True))


def downgrade():
    # Remove unlicensed_solar column from production_data table
    op.drop_column('production_data', 'unlicensed_solar') 