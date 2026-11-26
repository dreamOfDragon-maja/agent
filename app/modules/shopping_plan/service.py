from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product.repository import ProductRepository
from app.modules.shopping_plan.exceptions import ShoppingPlanNotFoundError
from app.modules.shopping_plan.repository import ShoppingPlanRepository
from app.modules.shopping_plan.schemas import (
    ShoppingPlanCreate,
    ShoppingPlanItemResponse,
    ShoppingPlanResponse,
)


class ShoppingPlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ShoppingPlanRepository(session)
        self.product_repository = ProductRepository(session)

    async def create_plan(
        self,
        user_id: int,
        data: ShoppingPlanCreate,
    ) -> UUID:
        try:
            plan = await self.repository.create(user_id=user_id, data=data)
            await self.session.commit()
            return plan.id
        except Exception:
            await self.session.rollback()
            raise

    async def get_plan(self, user_id: int, plan_id: UUID) -> ShoppingPlanResponse:
        plan = await self.repository.find_owned(plan_id, user_id)
        if plan is None:
            raise ShoppingPlanNotFoundError

        items = await self.repository.list_items(plan_id)
        products = await self.product_repository.find_by_ids(
            [item.product_id for item in items]
        )
        product_map = {product.id: product for product in products}

        item_responses: list[ShoppingPlanItemResponse] = []
        for item in items:
            product = product_map.get(item.product_id)
            unit_price = item.unit_price
            if unit_price is None and product is not None:
                unit_price = product.min_price
            item_responses.append(
                ShoppingPlanItemResponse(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=product.name if product else f"商品 {item.product_id}",
                    category=product.category if product else "",
                    brand=product.brand if product else None,
                    image_url=product.image_url if product else None,
                    unit_price=unit_price,
                    priority=item.priority,
                    recommendation_reason=item.recommendation_reason,
                    status=item.status,
                )
            )

        return ShoppingPlanResponse(
            id=plan.id,
            plan_name=plan.plan_name,
            summary=plan.summary,
            customer_profile=plan.customer_profile or {},
            total_budget=plan.total_budget,
            status=plan.status,
            items=item_responses,
        )
