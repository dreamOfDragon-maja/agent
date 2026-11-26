from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShoppingPlanItemCreate(BaseModel):
    """购物方案项"""

    product_id: int
    product_name: str = Field(description="商品名称")  # 用于方案展示
    category: str = Field(description="商品分类")  # 用于方案展示
    priority: int = Field(default=1, ge=1)
    recommendation_reason: str | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, description="商品参考单价")


class ShoppingPlanCreate(BaseModel):
    """购物方案"""

    plan_name: str = Field(min_length=1, max_length=120)
    summary: str | None = None
    customer_profile: dict[str, Any] = Field(default_factory=dict)
    items: list[ShoppingPlanItemCreate] = Field(min_length=1)


class ShoppingPlanItemResponse(BaseModel):
    """购物方案项响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: int
    product_name: str
    category: str
    brand: str | None = None
    image_url: str | None = None
    unit_price: Decimal | None = None
    priority: int
    recommendation_reason: str | None = None
    status: str


class ShoppingPlanResponse(BaseModel):
    """购物方案响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_name: str
    summary: str | None = None
    customer_profile: dict[str, Any] = Field(default_factory=dict)
    total_budget: Decimal | None = None
    status: str
    items: list[ShoppingPlanItemResponse] = Field(default_factory=list)


@dataclass(frozen=True)
class ShoppingAgentContext:
    """购物顾问 Agent 运行时上下文"""

    user_id: int
