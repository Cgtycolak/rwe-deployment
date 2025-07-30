"""Update update_id field to string.

Revision ID: 20240612000000
Revises: 20240501000000
Create Date: 2024-06-12 15:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20240612000000'
down_revision = '20240501000000'
branch_labels = None
depends_on = None


def upgrade():
    # Update update_id column to string (varchar) in all Meteologica tables
    op.alter_column('meteologica_unlicensed_solar', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_licensed_solar', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_wind', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_dam_hydro', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_runofriver_hydro', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_demand', 'update_id', 
                    existing_type=sa.INTEGER(), 
                    type_=sa.String(50),
                    nullable=True,
                    schema='meteologica')


def downgrade():
    # Revert update_id column back to integer in all Meteologica tables
    op.alter_column('meteologica_unlicensed_solar', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_licensed_solar', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_wind', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_dam_hydro', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_runofriver_hydro', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica')

    op.alter_column('meteologica_demand', 'update_id', 
                    existing_type=sa.String(50), 
                    type_=sa.INTEGER(),
                    nullable=True,
                    schema='meteologica') 