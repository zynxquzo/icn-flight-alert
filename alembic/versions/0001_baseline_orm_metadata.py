"""ORM 메타데이터 기준 초기 스키마(baseline).

기존 `Base.metadata.create_all`과 동일한 결과를 한 번에 적용합니다.
이후 변경은 `uv run alembic revision --autogenerate -m "설명"`으로 리비전을 만들고,
생성된 마이그레이션을 검토한 뒤 커밋하세요.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-27
"""

from alembic import op
from database import Base
import flight_alert.models  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
