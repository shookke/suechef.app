"""Add servings to meal

Revision ID: c28bc9056a38
Revises: 4b035285611d
Create Date: 2020-04-01 18:17:54.408173

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c28bc9056a38'
down_revision = '4b035285611d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meal', schema=None) as batch_op:
        batch_op.add_column(sa.Column('servings', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meal', schema=None) as batch_op:
        batch_op.drop_column('servings')

    # ### end Alembic commands ###