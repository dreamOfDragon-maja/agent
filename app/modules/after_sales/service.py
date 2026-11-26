from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.after_sales.exceptions import (
    AfterSalesOrderNotFoundError,
    AfterSalesOrderStateError,
)
from app.modules.after_sales.models import AfterSalesProgress, AfterSalesTicket
from app.modules.after_sales.repository import AfterSalesRepository
from app.modules.after_sales.schemas import AfterSalesTicketCreate
from app.modules.order.repository import OrderRepository


class AfterSalesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AfterSalesRepository(session)
        self.order_repository = OrderRepository(session)

    async def create_ticket(
        self,
        user_id: int,
        data: AfterSalesTicketCreate,
    ) -> UUID:
        order = await self.order_repository.find_owned(data.order_id, user_id)
        if order is None:
            raise AfterSalesOrderNotFoundError
        if order.status not in {"paid", "shipped", "completed"}:
            raise AfterSalesOrderStateError

        try:
            ticket = await self.repository.create_ticket(
                AfterSalesTicket(
                    user_id=user_id,
                    order_id=order.id,
                    product_id=order.product_id,
                    ticket_number=self._new_ticket_number(),
                    issue_type=data.issue_type,
                    issue_description=data.issue_description,
                    desired_resolution=data.desired_resolution,
                )
            )
            # 初始进度：申请已提交 -> 审核处理中
            self.repository.add_progress(
                AfterSalesProgress(
                    ticket_id=ticket.id,
                    node="提交申请",
                    status="done",
                    remark="售后申请提交成功",
                )
            )
            self.repository.add_progress(
                AfterSalesProgress(
                    ticket_id=ticket.id,
                    node="审核处理",
                    status="processing",
                )
            )
            await self.session.commit()
            return ticket.id
        except Exception:
            await self.session.rollback()
            raise

    async def list_by_user(self, user_id: int) -> list[AfterSalesTicket]:
        return await self.repository.list_by_user(user_id)

    async def list_progress(self, ticket_ids: list[UUID]) -> list[AfterSalesProgress]:
        return await self.repository.list_progress(ticket_ids)

    @staticmethod
    def _new_ticket_number() -> str:
        from datetime import datetime, timezone
        from uuid import uuid4

        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"AS{now}{uuid4().hex[:6].upper()}"
