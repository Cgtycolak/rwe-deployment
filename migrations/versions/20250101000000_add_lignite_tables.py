"""add lignite tables

Revision ID: 20250101000000
Revises: 20240612000000
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101000000'
down_revision = '20240612000000'
branch_labels = None
depends_on = None


def upgrade():
    # Create lignite_heatmap_data table
    op.create_table(
        'lignite_heatmap_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('plant_name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('version', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'hour', 'plant_name', 'version', 
                          name='lignite_heatmap_data_date_hour_plant_name_version_key')
    )
    
    # Create lignite_realtime_data table
    op.create_table(
        'lignite_realtime_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('plant_name', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'hour', 'plant_name', 
                          name='unique_lignite_realtime_record')
    )


def downgrade():
    # Drop lignite tables
    op.drop_table('lignite_realtime_data')
    op.drop_table('lignite_heatmap_data') 