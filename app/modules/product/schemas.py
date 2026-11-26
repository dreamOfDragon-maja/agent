from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductResponse(BaseModel):
    """商品响应结果"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    document_name: str
    category: str
    brand: str
    image_url: str | None = None
    description: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    target_group: str | None = None
    highlights: list[str] = Field(default_factory=list)
    status: str

    @field_validator("highlights", mode="before")
    @classmethod
    def default_highlights(cls, value: list[str] | None) -> list[str]:
        return value or []
