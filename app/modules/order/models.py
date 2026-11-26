from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin
# 注册 users、products、shopping_plans、shopping_plan_items 表到 Base.metadata
from app.modules.user.models import User  # noqa: F401
from app.modules.product.models import Product  # noqa: F401
from app.modules.shopping_plan.models import ShoppingPlan, ShoppingPlanItem  # noqa: F401


class ShopOrder(Base, CreateAtMixin, UpdateAtMixin):
    """商城订单"""

    __tablename__ = "shop_orders"
    __table_args__ = (
        Index(
            "uk_shop_orders_active_plan_item",
            "plan_item_id",
            unique=True,
            postgresql_where=text(
                "plan_item_id IS NOT NULL AND status <> 'cancelled'"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
    )
    order_number: Mapped[str] = mapped_column(String(40), unique=True)
    plan_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopping_plans.id", ondelete="SET NULL"),
    )
    plan_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shopping_plan_items.id", ondelete="SET NULL"),
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending_payment",
        server_default="pending_payment",
    )
    shipping_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    payment_method: Mapped[str] = mapped_column(
        String(30),
        default="online",
        server_default="online",
    )
    delivery_method: Mapped[str] = mapped_column(
        String(30),
        default="standard",
        server_default="standard",
    )
    invoice_type: Mapped[str] = mapped_column(
        String(30),
        default="none",
        server_default="none",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
