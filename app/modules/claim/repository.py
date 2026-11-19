from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.claim.models import ClaimCase, ClaimProgress

class ClaimRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_case(self, case: ClaimCase) -> ClaimCase:
        self.session.add(case)
        await self.session.flush()
        return case

    def add_progress(self, progress: ClaimProgress) -> None:
        self.session.add(progress)

    async def list_by_user(self, user_id: int) -> list[ClaimCase]:
        result = await self.session.scalars(
            select(ClaimCase)
            .where(ClaimCase.user_id == user_id)
            .order_by(ClaimCase.created_at.desc())
        )
        return list(result.all())

    async def list_progress(self, case_ids: list) -> list[ClaimProgress]:
        result = await self.session.scalars(
            select(ClaimProgress)
            .where(ClaimProgress.case_id.in_(case_ids))
            .order_by(ClaimProgress.created_at.asc())
        )
        return list(result.all())
