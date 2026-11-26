from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.order.exceptions import (
    OrderItemNotAvailableError,
    OrderNotFoundError,
    OrderStateError,
)
from app.modules.order.models import ShopOrder
from app.modules.order.repository import OrderRepository
from app.modules.order.schemas import OrderCreate, OrderResponse
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.shopping_plan.repository import ShoppingPlanRepository


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = OrderRepository(session)
        self.product_repository = ProductRepository(session)
        self.plan_repository = ShoppingPlanRepository(session)

    async def create_order(self, user_id: int, data: OrderCreate) -> OrderResponse:
        # 1.幂等：同一用户、同一 key 只创建一次订单
        if data.idempotency_key:
            existing = await self.repository.find_by_idempotency_key(
                user_id,
                data.idempotency_key,
            )
            if existing is not None:
                product = await self._load_product(existing.product_id)
                return self._to_response(existing, product)

        # 2.同一方案项已有未取消订单时直接返回，支持支付失败后刷新重试
        existing_order = await self.repository.find_active_by_plan_item(
            user_id,
            data.plan_id,
            data.plan_item_id,
        )
        if existing_order is not None:
            product = await self._load_product(existing_order.product_id)
            return self._to_response(existing_order, product)

        # 3.校验方案、方案项、商品归属
        plan = await self.plan_repository.find_owned(data.plan_id, user_id)
        if plan is None:
            raise OrderItemNotAvailableError

        item = await self.plan_repository.get_item(data.plan_id, data.plan_item_id)
        if item is None or item.status != "pending":
            raise OrderItemNotAvailableError

        product = await self.product_repository.find_by_ids([item.product_id])
        if not product or product[0].status != "active":
            raise OrderItemNotAvailableError

        if item.unit_price is None and product[0].min_price is None:
            raise OrderStateError

        unit_price = item.unit_price or product[0].min_price
        assert unit_price is not None
        total_amount = (unit_price * data.quantity).quantize(Decimal("0.01"))

        # 4.创建待支付订单
        order = ShopOrder(
            user_id=user_id,
            order_number=self._new_order_number(),
            plan_id=data.plan_id,
            plan_item_id=item.id,
            product_id=item.product_id,
            quantity=data.quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            status="pending_payment",
            shipping_info=data.shipping_info.model_dump(),
            payment_method=data.payment_method,
            delivery_method=data.delivery_method,
            invoice_type=data.invoice_type,
            idempotency_key=data.idempotency_key,
        )
        try:
            await self.repository.create(order)
            await self.session.commit()
            await self.session.refresh(order)
        except IntegrityError:
            # 并发下同一方案项可能被重复下单，由数据库唯一索引兜底
            await self.session.rollback()
            raise OrderItemNotAvailableError
        except Exception:
            await self.session.rollback()
            raise
        product = await self._load_product(order.product_id)
        return self._to_response(order, product)

    async def pay_order(self, user_id: int, order_id: UUID) -> OrderResponse:
        order = await self.repository.find_owned(order_id, user_id)
        if order is None:
            raise OrderNotFoundError
        if order.status != "pending_payment":
            raise OrderStateError

        try:
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)
            if order.plan_id and order.plan_item_id:
                item = await self.plan_repository.get_item(
                    order.plan_id,
                    order.plan_item_id,
                )
                if item is not None:
                    await self.plan_repository.mark_item_ordered(item)
                    # 会话关闭了 autoflush，先显式刷新，确保方案状态计算读到最新值
                    await self.session.flush()
                    await self.plan_repository.refresh_plan_status(
                        order.plan_id,
                        user_id,
                    )
            await self.session.commit()
            await self.session.refresh(order)
        except Exception:
            await self.session.rollback()
            raise
        product = await self._load_product(order.product_id)
        return self._to_response(order, product)

    async def get_order(self, user_id: int, order_id: UUID) -> OrderResponse:
        order = await self.repository.find_owned(order_id, user_id)
        if order is None:
            raise OrderNotFoundError
        product = await self._load_product(order.product_id)
        return self._to_response(order, product)

    async def list_orders(self, user_id: int) -> list[OrderResponse]:
        orders = await self.repository.list_by_user(user_id)
        products = await self.product_repository.find_by_ids(
            [order.product_id for order in orders]
        )
        product_map = {product.id: product for product in products}
        return [
            self._to_response(order, product_map.get(order.product_id))
            for order in orders
        ]

    async def _load_product(self, product_id: int) -> Product | None:
        products = await self.product_repository.find_by_ids([product_id])
        return products[0] if products else None

    @staticmethod
    def _to_response(
        order: ShopOrder,
        product: Product | None,
    ) -> OrderResponse:
        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            product_id=order.product_id,
            product_name=product.name if product else None,
            product_category=product.category if product else None,
            product_brand=product.brand if product else None,
            quantity=order.quantity,
            unit_price=order.unit_price,
            total_amount=order.total_amount,
            shipping_info=order.shipping_info or {},
            payment_method=order.payment_method,
            delivery_method=order.delivery_method,
            invoice_type=order.invoice_type,
            created_at=order.created_at,
            paid_at=order.paid_at,
        )

    @staticmethod
    def _new_order_number() -> str:
        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"SM{now}{uuid4().hex[:6].upper()}"
