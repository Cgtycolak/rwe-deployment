"""add realtime tables

Revision ID: 20240304_add_realtime_tables
Revises: dc9103d3fe4b  # This should be your last migration's revision ID
Create Date: 2024-03-04 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '20240304_add_realtime_tables'
down_revision = 'dc9103d3fe4b'  # Replace with your last migration's revision ID
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('hydro_realtime_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('plant_name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'hour', 'plant_name', name='unique_hydro_realtime_record')
    )
    
    op.create_table('natural_gas_realtime_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('plant_name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'hour', 'plant_name', name='unique_natural_gas_realtime_record')
    )

def downgrade():
    op.drop_table('hydro_realtime_data')
    op.drop_table('natural_gas_realtime_data') 