"""remove installed_capacity column from licensed_solar_data

Revision ID: 20250813000001
Revises: 20250101000004
Create Date: 2025-08-13 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250813000001'
down_revision = '20250101000004'
branch_labels = None
depends_on = None

def upgrade():
    # Drop the installed_capacity column
    with op.batch_alter_table('licensed_solar_data', schema=None) as batch_op:
        batch_op.drop_column('installed_capacity')

def downgrade():
    # Add back the installed_capacity column if needed
    with op.batch_alter_table('licensed_solar_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('installed_capacity', sa.Float(), nullable=True)) 