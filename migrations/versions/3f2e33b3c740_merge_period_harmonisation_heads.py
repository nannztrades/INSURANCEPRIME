"""merge period harmonisation heads

Revision ID: 3f2e33b3c740
Revises: 20260125_1601_period_yyyy_mm, 20260125_1602_period_yyyy_mm_v2
Create Date: 2026-01-25 15:58:04.408160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f2e33b3c740'
down_revision: Union[str, None] = ('20260125_1601_period_yyyy_mm', '20260125_1602_period_yyyy_mm_v2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
