from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.infra.database import get_session
from app.modules.shopping_plan.schemas import ShoppingPlanResponse
from app.modules.shopping_plan.service import ShoppingPlanService

router = APIRouter(
    prefix="/api/v1/shopping-plans",
    tags=["购物方案接口"],
)


def get_shopping_plan_service(
    session: AsyncSession = Depends(get_session),
) -> ShoppingPlanService:
    return ShoppingPlanService(session)


@router.get(
    "/{plan_id}",
    response_model=ShoppingPlanResponse,
    summary="查询购物方案详情",
)
async def get_shopping_plan(
    plan_id: UUID,
    user: CurrentUser,
    service: ShoppingPlanService = Depends(get_shopping_plan_service),
) -> ShoppingPlanResponse:
    return await service.get_plan(user.id, plan_id)
