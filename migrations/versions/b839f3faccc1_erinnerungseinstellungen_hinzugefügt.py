"""Erinnerungseinstellungen hinzugefügt

Revision ID: b839f3faccc1
Revises: e1fffd707d8f
Create Date: 2026-09-01 08:24:25.194780

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b839f3faccc1'
down_revision = 'e1fffd707d8f'
branch_labels = None
depends_on = None


def upgrade():
    # Die shift-Spalten (daily_reminder_sent_at, shift_reminder_sent_at) kamen
    # durch die fruehere Verschachtelung lokal nie an und werden erst in
    # 62c7ebde987b angelegt — hier nicht anlegen, sonst Duplikat auf Postgres
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('daily_reminder_enabled', sa.Boolean(), nullable=False, server_default="true"))
        batch_op.add_column(sa.Column('daily_reminder_time', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('shift_reminder_enabled', sa.Boolean(), nullable=False, server_default="true"))
        batch_op.add_column(sa.Column('shift_reminder_lead_minutes', sa.Integer(), nullable=False, server_default="60"))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('shift_reminder_lead_minutes')
        batch_op.drop_column('shift_reminder_enabled')
        batch_op.drop_column('daily_reminder_time')
        batch_op.drop_column('daily_reminder_enabled')
