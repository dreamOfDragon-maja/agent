from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin

# 注册 users、products 表到 Base.metadata，否则外键无法解析
from app.modules.user.models import User  # noqa: F401
from app.modules.product.models import Product  # noqa: F401

class ClaimCase(Base, CreateAtMixin, UpdateAtMixin):
    """理赔案件"""

    __tablename__ = "claim_cases"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
    )
    policy_no: Mapped[str | None] = mapped_column(String(100))
    incident_type: Mapped[str] = mapped_column(String(30))
    incident_description: Mapped[str] = mapped_column(Text)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(
        String(30),
        default="submitted",
        server_default="submitted",
    )

class ClaimProgress(Base, CreateAtMixin):
    """理赔进度"""

    __tablename__ = "claim_progress"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("claim_cases.id", ondelete="CASCADE"),
    )
    node: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(30),
        default="processing",
        server_default="processing",
    )
    remark: Mapped[str | None] = mapped_column(Text)
