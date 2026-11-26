from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin
# 注册 users、products、shop_orders 表到 Base.metadata，否则外键无法解析
from app.modules.user.models import User  # noqa: F401
from app.modules.product.models import Product  # noqa: F401
from app.modules.order.models import ShopOrder  # noqa: F401


class AfterSalesTicket(Base, CreateAtMixin, UpdateAtMixin):
    """售后工单"""

    __tablename__ = "after_sales_tickets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
    )
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("shop_orders.id"),
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id"),
    )
    ticket_number: Mapped[str] = mapped_column(String(40), unique=True)
    issue_type: Mapped[str] = mapped_column(String(30))
    issue_description: Mapped[str] = mapped_column(Text)
    desired_resolution: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30),
        default="submitted",
        server_default="submitted",
    )


class AfterSalesProgress(Base, CreateAtMixin):
    """售后工单进度"""

    __tablename__ = "after_sales_progress"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ticket_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("after_sales_tickets.id", ondelete="CASCADE"),
    )
    node: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(30),
        default="processing",
        server_default="processing",
    )
    remark: Mapped[str | None] = mapped_column(Text)
