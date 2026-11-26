from decimal import Decimal

from sqlalchemy import ARRAY, BigInteger, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import Base, CreateAtMixin, UpdateAtMixin


class Product(Base, CreateAtMixin, UpdateAtMixin):
    """商城商品"""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    document_name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(50))
    brand: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    target_group: Mapped[str | None] = mapped_column(String(300))
    highlights: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        server_default="active",
    )