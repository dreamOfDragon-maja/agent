from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder
from app.modules.insurance_plan.models import InsurancePlan, InsurancePlanItem
from app.modules.insurance_plan.repository import InsurancePlanRepository
from app.modules.insurance_plan.schemas import InsurancePlanCreate


class InsurancePlanService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = InsurancePlanRepository(session)

    async def create_plan(
        self,
        user_id: int,
        data: InsurancePlanCreate,
    ) -> UUID:
        try:
            plan = await self.repository.create(
                user_id=user_id,
                data=data,
            )
            await self.session.commit()
            return plan.id
        except Exception:
            await self.session.rollback()
            raise

    async def list_insured_by_user(self, user_id: int) -> list[dict]:
        """查询用户名下已投保（status=insured）的方案项及其关联产品。"""
        from sqlalchemy import select, join
        from app.modules.product.models import Product
        stmt = (
            select(
                InsurancePlanItem.product_id,
                InsurancePlanItem.recommendation_reason,
                InsurancePlanItem.annual_premium_budget,
                Product.name.label("product_name"),
                Product.category.label("product_category"),
                Product.clause_name,
            )
            .select_from(
                join(
                    InsurancePlanItem,
                    Product,
                    InsurancePlanItem.product_id == Product.id,
                )
                .join(
                    InsurancePlan,
                    InsurancePlanItem.plan_id == InsurancePlan.id,
                )
            )
            .where(
                InsurancePlan.user_id == user_id,
                InsurancePlanItem.status == "insured",
                InsurancePlan.status == "insured",
            )
        )
        result = await self.session.execute(stmt)
        rows = result.mappings().all()
        return [jsonable_encoder(row) for row in rows]