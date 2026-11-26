from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.after_sales.models import AfterSalesProgress, AfterSalesTicket


class AfterSalesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ticket(self, ticket: AfterSalesTicket) -> AfterSalesTicket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    def add_progress(self, progress: AfterSalesProgress) -> None:
        self.session.add(progress)

    async def list_by_user(self, user_id: int) -> list[AfterSalesTicket]:
        result = await self.session.scalars(
            select(AfterSalesTicket)
            .where(AfterSalesTicket.user_id == user_id)
            .order_by(AfterSalesTicket.created_at.desc())
        )
        return list(result.all())

    async def list_progress(self, ticket_ids: list[UUID]) -> list[AfterSalesProgress]:
        if not ticket_ids:
            return []
        result = await self.session.scalars(
            select(AfterSalesProgress)
            .where(AfterSalesProgress.ticket_id.in_(ticket_ids))
            .order_by(AfterSalesProgress.created_at.asc())
        )
        return list(result.all())
