from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin
# 注册 users、products 表到 Base.metadata，否则外键无法解析
from app.modules.user.models import User  # noqa: F401
from app.modules.product.models import Product  # noqa: F401


class ShoppingPlan(Base, CreateAtMixin, UpdateAtMixin):
    """用户购物方案"""

    __tablename__ = "shopping_plans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
    )
    plan_name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str | None] = mapped_column(Text)
    customer_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    total_budget: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2)
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        server_default="active",
    )


class ShoppingPlanItem(Base, CreateAtMixin, UpdateAtMixin):
    """购物方案中的商品项"""

    __tablename__ = "shopping_plan_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopping_plans.id", ondelete="CASCADE"),
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )
    recommendation_reason: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2)
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        server_default="pending",
    )
