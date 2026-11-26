from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ShippingInfo(BaseModel):
    """收货信息"""

    recipient_name: str = Field(min_length=1, max_length=40)
    phone: str = Field(min_length=11, max_length=20)
    address: str = Field(min_length=5, max_length=300)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = value.replace(" ", "").replace("-", "")
        if not cleaned.isdigit() or len(cleaned) not in (11, 13):
            raise ValueError("请输入有效的手机号")
        return cleaned


class OrderCreate(BaseModel):
    """创建订单"""

    plan_id: UUID
    plan_item_id: UUID
    quantity: int = Field(default=1, ge=1, le=99)
    shipping_info: ShippingInfo
    payment_method: Literal["online", "cod"] = "online"
    delivery_method: Literal["standard", "express"] = "standard"
    invoice_type: Literal["none", "personal", "company"] = "none"
    idempotency_key: str | None = Field(default=None, max_length=80)


class OrderResponse(BaseModel):
    """订单响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    status: str
    product_id: int
    product_name: str | None = None
    product_category: str | None = None
    product_brand: str | None = None
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    shipping_info: dict
    payment_method: str
    delivery_method: str
    invoice_type: str
    created_at: datetime
    paid_at: datetime | None = None
