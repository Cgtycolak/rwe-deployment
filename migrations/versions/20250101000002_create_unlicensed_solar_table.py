"""create unlicensed solar table

Revision ID: 20250101000002
Revises: 20250101000001
Create Date: 2025-01-01 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250101000002'
down_revision = '20250101000001'
branch_labels = None
depends_on = None


def upgrade():
    # Create unlicensed_solar_data table
    op.create_table('unlicensed_solar_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('datetime', sa.DateTime(), nullable=False),
        sa.Column('unlicensed_solar', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('datetime')
    )
    
    # Create index on datetime for faster lookups
    op.create_index('ix_unlicensed_solar_data_datetime', 'unlicensed_solar_data', ['datetime'])


def downgrade():
    # Drop the table
    op.drop_index('ix_unlicensed_solar_data_datetime', 'unlicensed_solar_data')
    op.drop_table('unlicensed_solar_data') 