from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.shopping_plan.models import ShoppingPlan, ShoppingPlanItem
from app.modules.shopping_plan.schemas import ShoppingPlanCreate


class ShoppingPlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        data: ShoppingPlanCreate,
    ) -> ShoppingPlan:
        # 1.计算方案参考总价
        item_prices = [
            item.unit_price
            for item in data.items
            if item.unit_price is not None
        ]
        total_budget = sum(item_prices, Decimal("0")) if item_prices else None

        # 2.保存购物方案
        plan = ShoppingPlan(
            user_id=user_id,
            plan_name=data.plan_name,
            summary=data.summary,
            customer_profile=data.customer_profile,
            total_budget=total_budget,
        )
        self.session.add(plan)
        await self.session.flush()

        # 3.保存方案项
        plan_items = [
            ShoppingPlanItem(
                plan_id=plan.id,
                product_id=item.product_id,
                priority=item.priority,
                recommendation_reason=item.recommendation_reason,
                unit_price=item.unit_price,
            )
            for item in data.items
        ]
        self.session.add_all(plan_items)
        return plan

    async def find_owned(self, plan_id: UUID, user_id: int) -> ShoppingPlan | None:
        return await self.session.scalar(
            select(ShoppingPlan).where(
                ShoppingPlan.id == plan_id,
                ShoppingPlan.user_id == user_id,
            )
        )

    async def list_items(self, plan_id: UUID) -> list[ShoppingPlanItem]:
        result = await self.session.scalars(
            select(ShoppingPlanItem)
            .where(ShoppingPlanItem.plan_id == plan_id)
            .order_by(ShoppingPlanItem.priority.asc(), ShoppingPlanItem.id.asc())
        )
        return list(result.all())

    async def get_item(
        self,
        plan_id: UUID,
        item_id: UUID,
    ) -> ShoppingPlanItem | None:
        return await self.session.scalar(
            select(ShoppingPlanItem).where(
                ShoppingPlanItem.id == item_id,
                ShoppingPlanItem.plan_id == plan_id,
            )
        )

    async def mark_item_ordered(self, item: ShoppingPlanItem) -> None:
        item.status = "ordered"

    async def refresh_plan_status(self, plan_id: UUID, user_id: int) -> None:
        """所有方案项均已下单时，把方案标记为 ordered。"""

        plan = await self.find_owned(plan_id, user_id)
        if plan is None:
            return
        items = await self.list_items(plan_id)
        if items and all(item.status in {"ordered", "fulfilled"} for item in items):
            plan.status = "ordered"
