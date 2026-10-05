"""Add confirmed_at to shift (team member confirms a leader's change)

Revision ID: c7e1a2b3d4f5
Revises: b5d2e8c1f03a
Create Date: 2026-10-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e1a2b3d4f5'
down_revision = 'b5d2e8c1f03a'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shift', sa.Column('confirmed_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('shift', 'confirmed_at')
