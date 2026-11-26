from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.infra.database import get_session
from app.modules.order.schemas import OrderCreate, OrderResponse
from app.modules.order.service import OrderService

router = APIRouter(prefix="/api/v1/orders", tags=["订单接口"])


def get_order_service(session: AsyncSession = Depends(get_session)) -> OrderService:
    return OrderService(session)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="从购物方案项创建订单",
)
async def create_order(
    request: OrderCreate,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return await service.create_order(user.id, request)


@router.get("", response_model=list[OrderResponse], summary="查询我的订单")
async def list_orders(
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> list[OrderResponse]:
    return await service.list_orders(user.id)


@router.get("/{order_id}", response_model=OrderResponse, summary="查询订单详情")
async def get_order(
    order_id: UUID,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    return await service.get_order(user.id, order_id)


@router.post(
    "/{order_id}/pay",
    response_model=OrderResponse,
    summary="确认支付（支付网关接入点）",
)
async def pay_order(
    order_id: UUID,
    user: CurrentUser,
    service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    """演示环境直接标记支付成功；接入支付网关后由支付回调调用同一服务方法。"""

    return await service.pay_order(user.id, order_id)
