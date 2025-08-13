"""remove unlicensed solar from production data

Revision ID: 20250101000003
Revises: 20250101000002
Create Date: 2025-01-01 00:00:03.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250101000003'
down_revision = '20250101000002'
branch_labels = None
depends_on = None


def upgrade():
    # Remove unlicensed_solar column from production_data table
    op.drop_column('production_data', 'unlicensed_solar')


def downgrade():
    # Add unlicensed_solar column back to production_data table
    op.add_column('production_data', sa.Column('unlicensed_solar', sa.Float(), nullable=True)) 