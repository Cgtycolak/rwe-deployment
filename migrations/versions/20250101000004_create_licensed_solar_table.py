"""create licensed solar table

Revision ID: 20250101000004
Revises: 20250101000003
Create Date: 2025-01-01 00:00:04.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250101000004'
down_revision = '20250101000003'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = inspector.get_table_names()
    if 'licensed_solar_data' not in tables:
        op.create_table('licensed_solar_data',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('datetime', sa.DateTime(), nullable=False),
            sa.Column('licensed_solar', sa.Float(), nullable=False),
            sa.Column('installed_capacity', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('datetime')
        )
        op.create_index(op.f('ix_licensed_solar_data_datetime'), 'licensed_solar_data', ['datetime'], unique=False)
    else:
        # Ensure the datetime index exists
        existing_indexes = [ix['name'] for ix in inspector.get_indexes('licensed_solar_data')]
        if op.f('ix_licensed_solar_data_datetime') not in existing_indexes and 'ix_licensed_solar_data_datetime' not in existing_indexes:
            op.create_index(op.f('ix_licensed_solar_data_datetime'), 'licensed_solar_data', ['datetime'], unique=False)

def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = inspector.get_table_names()
    if 'licensed_solar_data' in tables:
        existing_indexes = [ix['name'] for ix in inspector.get_indexes('licensed_solar_data')]
        if op.f('ix_licensed_solar_data_datetime') in existing_indexes:
            op.drop_index(op.f('ix_licensed_solar_data_datetime'), table_name='licensed_solar_data')
        elif 'ix_licensed_solar_data_datetime' in existing_indexes:
            op.drop_index('ix_licensed_solar_data_datetime', table_name='licensed_solar_data')
        op.drop_table('licensed_solar_data')