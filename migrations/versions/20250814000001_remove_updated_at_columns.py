"""remove updated_at columns from solar tables

Revision ID: 20250814000001
Revises: 20250813000001
Create Date: 2025-08-14 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250814000001'
down_revision = '20250813000001'
branch_labels = None
depends_on = None

def upgrade():
    # Remove updated_at column from unlicensed_solar_data table
    with op.batch_alter_table('unlicensed_solar_data', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
    
    # Remove updated_at column from licensed_solar_data table
    with op.batch_alter_table('licensed_solar_data', schema=None) as batch_op:
        batch_op.drop_column('updated_at')

def downgrade():
    # Add back the updated_at columns if needed
    with op.batch_alter_table('unlicensed_solar_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    with op.batch_alter_table('licensed_solar_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True)) 