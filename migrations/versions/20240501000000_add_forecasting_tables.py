"""add_forecasting_tables

Revision ID: 20240501000000
Revises: 20240423000000
Create Date: 2024-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20240501000000'
down_revision = '20240423000000'
branch_labels = None
depends_on = None


def upgrade():
    # Create meteologica schema if it doesn't exist
    op.execute('CREATE SCHEMA IF NOT EXISTS meteologica')
    
    # Create epias schema if it doesn't exist
    op.execute('CREATE SCHEMA IF NOT EXISTS epias')
    
    # Create meteologica_unlicensed_solar table
    op.create_table('meteologica_unlicensed_solar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_unlicensed_solar_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create meteologica_licensed_solar table
    op.create_table('meteologica_licensed_solar',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_licensed_solar_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create meteologica_wind table
    op.create_table('meteologica_wind',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_wind_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create meteologica_dam_hydro table
    op.create_table('meteologica_dam_hydro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_dam_hydro_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create meteologica_runofriver_hydro table
    op.create_table('meteologica_runofriver_hydro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_runofriver_hydro_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create meteologica_demand table
    op.create_table('meteologica_demand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('forecasted', sa.Float(), nullable=True),
        sa.Column('hour_0', sa.Float(), nullable=True),
        sa.Column('hour_1', sa.Float(), nullable=True),
        sa.Column('hour_2', sa.Float(), nullable=True),
        sa.Column('hour_3', sa.Float(), nullable=True),
        sa.Column('hour_4', sa.Float(), nullable=True),
        sa.Column('hour_5', sa.Float(), nullable=True),
        sa.Column('hour_6', sa.Float(), nullable=True),
        sa.Column('hour_7', sa.Float(), nullable=True),
        sa.Column('hour_8', sa.Float(), nullable=True),
        sa.Column('hour_9', sa.Float(), nullable=True),
        sa.Column('hour_10', sa.Float(), nullable=True),
        sa.Column('hour_11', sa.Float(), nullable=True),
        sa.Column('hour_12', sa.Float(), nullable=True),
        sa.Column('update_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_meteologica_demand_timestamp', 'timestamp'),
        schema='meteologica'
    )
    
    # Create epias_yal table for system direction data
    op.create_table('epias_yal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('net', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_epias_yal_date', 'date'),
        schema='epias'
    )


def downgrade():
    # Drop tables
    op.drop_table('epias_yal', schema='epias')
    op.drop_table('meteologica_demand', schema='meteologica')
    op.drop_table('meteologica_runofriver_hydro', schema='meteologica')
    op.drop_table('meteologica_dam_hydro', schema='meteologica')
    op.drop_table('meteologica_wind', schema='meteologica')
    op.drop_table('meteologica_licensed_solar', schema='meteologica')
    op.drop_table('meteologica_unlicensed_solar', schema='meteologica')
    
    # Drop schemas if empty
    op.execute('DROP SCHEMA IF EXISTS meteologica CASCADE')
    op.execute('DROP SCHEMA IF EXISTS epias CASCADE') 