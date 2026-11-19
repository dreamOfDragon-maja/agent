from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.claim.models import ClaimCase, ClaimProgress
from app.modules.claim.repository import ClaimRepository
from app.modules.claim.schemas import ClaimCaseCreate

class ClaimService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ClaimRepository(session)

    async def create_claim(
        self,
        user_id: int,
        data: ClaimCaseCreate,
    ) -> UUID:
        try:
            case = await self.repository.create_case(
                ClaimCase(
                    user_id=user_id,
                    product_id=data.product_id,
                    policy_no=data.policy_no,
                    incident_type=data.incident_type,
                    incident_description=data.incident_description,
                    incident_date=data.incident_date,
                    claim_amount=data.claim_amount,
                )
            )
            # 初始进度：报案完成 -> 受理审核中
            self.repository.add_progress(
                ClaimProgress(case_id=case.id, node="报案", status="done", remark="报案成功")
            )
            self.repository.add_progress(
                ClaimProgress(case_id=case.id, node="受理审核", status="processing")
            )
            await self.session.commit()
            return case.id
        except Exception:
            await self.session.rollback()
            raise

    async def list_by_user(self, user_id: int) -> list[ClaimCase]:
        return await self.repository.list_by_user(user_id)

    async def list_progress(self, case_ids: list) -> list[ClaimProgress]:
        if not case_ids:
            return []
        return await self.repository.list_progress(case_ids)
