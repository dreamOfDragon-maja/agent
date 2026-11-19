from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

class ClaimCaseCreate(BaseModel):
    """理赔报案信息"""

    product_id: int = Field(description="出险对应的保险产品ID")
    incident_type: str = Field(description="出险类型，如 illness(疾病) 或 accident(意外)")
    incident_description: str = Field(description="出险经过描述")
    incident_date: datetime = Field(description="出险发生时间")
    claim_amount: Decimal | None = Field(default=None, ge=0, description="申请理赔金额")
    policy_no: str | None = Field(default=None, max_length=100, description="保单号，可选")
