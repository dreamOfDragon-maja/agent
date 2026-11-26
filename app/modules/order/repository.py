from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.order.models import ShopOrder


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, order: ShopOrder) -> ShopOrder:
        self.session.add(order)
        await self.session.flush()
        return order

    async def find_owned(self, order_id: UUID, user_id: int) -> ShopOrder | None:
        return await self.session.scalar(
            select(ShopOrder).where(
                ShopOrder.id == order_id,
                ShopOrder.user_id == user_id,
            )
        )

    async def find_by_idempotency_key(
        self,
        user_id: int,
        idempotency_key: str,
    ) -> ShopOrder | None:
        return await self.session.scalar(
            select(ShopOrder).where(
                ShopOrder.user_id == user_id,
                ShopOrder.idempotency_key == idempotency_key,
            )
        )

    async def find_active_by_plan_item(
        self,
        user_id: int,
        plan_id: UUID,
        plan_item_id: UUID,
    ) -> ShopOrder | None:
        """同一方案项已有未取消订单时优先返回，避免刷新页面后重复下单。"""

        return await self.session.scalar(
            select(ShopOrder)
            .where(
                ShopOrder.user_id == user_id,
                ShopOrder.plan_id == plan_id,
                ShopOrder.plan_item_id == plan_item_id,
                ShopOrder.status != "cancelled",
            )
            .order_by(ShopOrder.created_at.desc())
        )

    async def list_by_user(self, user_id: int) -> list[ShopOrder]:
        result = await self.session.scalars(
            select(ShopOrder)
            .where(ShopOrder.user_id == user_id)
            .order_by(ShopOrder.created_at.desc())
        )
        return list(result.all())
