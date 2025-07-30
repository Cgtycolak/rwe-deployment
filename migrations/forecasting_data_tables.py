"""
Migration to create forecasting data tables.
This migration creates the necessary schema and tables for storing forecasting data.
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic
revision = '001_forecasting_data_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create meteologica schema if it doesn't exist
    op.execute('CREATE SCHEMA IF NOT EXISTS meteologica')
    
    # Create epias schema if it doesn't exist
    op.execute('CREATE SCHEMA IF NOT EXISTS epias')
    
    # Create unlicensed solar table
    op.create_table(
        'meteologica_unlicensed_solar',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create licensed solar table
    op.create_table(
        'meteologica_licensed_solar',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create wind table
    op.create_table(
        'meteologica_wind',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create dam hydro table
    op.create_table(
        'meteologica_dam_hydro',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create run of river hydro table
    op.create_table(
        'meteologica_runofriver_hydro',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create demand table
    op.create_table(
        'meteologica_demand',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
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
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='meteologica'
    )
    
    # Create system direction table
    op.create_table(
        'epias_yal',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('date', sa.DateTime(), nullable=False, index=True),
        sa.Column('net', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow),
        schema='epias'
    )


def downgrade():
    # Drop tables
    op.drop_table('meteologica_unlicensed_solar', schema='meteologica')
    op.drop_table('meteologica_licensed_solar', schema='meteologica')
    op.drop_table('meteologica_wind', schema='meteologica')
    op.drop_table('meteologica_dam_hydro', schema='meteologica')
    op.drop_table('meteologica_runofriver_hydro', schema='meteologica')
    op.drop_table('meteologica_demand', schema='meteologica')
    op.drop_table('epias_yal', schema='epias')
    
    # Drop schemas if empty
    op.execute('DROP SCHEMA IF EXISTS meteologica CASCADE')
    op.execute('DROP SCHEMA IF EXISTS epias CASCADE') 