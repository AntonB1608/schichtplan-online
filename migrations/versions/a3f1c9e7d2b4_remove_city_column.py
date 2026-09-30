"""Remove city column, timezone is derived from the browser

Revision ID: a3f1c9e7d2b4
Revises: b927468cc27a
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f1c9e7d2b4'
down_revision = 'b927468cc27a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('city')


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.VARCHAR(), nullable=True))
