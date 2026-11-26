from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AfterSalesTicketCreate(BaseModel):
    """售后申请信息"""

    order_id: UUID = Field(description="发生售后的订单 ID")
    issue_type: Literal["return", "exchange", "repair", "refund", "other"] = Field(
        description="问题类型：return(退货)、exchange(换货)、repair(维修)、refund(退款)、other(其他)"
    )
    issue_description: str = Field(
        min_length=10,
        max_length=2000,
        description="问题经过描述，包括商品问题、发生时间和已尝试的处理",
    )
    desired_resolution: str | None = Field(
        default=None,
        max_length=500,
        description="用户期望的处理方式",
    )
