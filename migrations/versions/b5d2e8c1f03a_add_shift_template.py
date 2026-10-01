"""Add shift_template table for reusable shift templates

Revision ID: b5d2e8c1f03a
Revises: a3f1c9e7d2b4
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5d2e8c1f03a'
down_revision = 'a3f1c9e7d2b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'shift_template',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=30), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('start_time', sa.String(), nullable=True),
        sa.Column('end_time', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'],
                                name=op.f('fk_shift_template_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shift_template')),
    )


def downgrade():
    op.drop_table('shift_template')
