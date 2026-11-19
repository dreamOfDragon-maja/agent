import json

from langchain.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from app.infra.database import AsyncSessionFactory
from app.modules.claim.schemas import ClaimCaseCreate
from app.modules.claim.service import ClaimService
from app.modules.insurance_plan.schemas import InsuranceAgentContext

@tool
async def create_claim_report(
    claim: ClaimCaseCreate,
    runtime: ToolRuntime[InsuranceAgentContext],
) -> dict[str, str]:
    """用户确认出险信息后，提交理赔报案。报案前必须已收集齐全出险产品、出险类型、出险时间、出险经过等信息。"""

    decision = interrupt(
        {
            "claim": claim.model_dump(mode="json"),
            "confirm_info": "是否确认提交本次理赔报案？",
            "action": ["approve", "reject"],
        }
    )
    if decision.get("action") != "approve":
        return {"message": f"用户取消报案, 原因:{decision.get('reject_reason')}"}

    async with AsyncSessionFactory() as session:
        service = ClaimService(session)
        case_id = await service.create_claim(
            user_id=runtime.context.user_id,
            data=claim,
        )

    return {
        "case_id": str(case_id),
        "message": "理赔报案提交成功",
    }

@tool
async def query_claim_progress(
    runtime: ToolRuntime[InsuranceAgentContext],
) -> str:
    """查询当前用户的理赔案件及其处理进度。"""

    async with AsyncSessionFactory() as session:
        service = ClaimService(session)
        cases = await service.list_by_user(runtime.context.user_id)
        if not cases:
            return "当前暂无理赔记录。"

        progress = await service.list_progress([case.id for case in cases])
        progress_map: dict = {}
        for item in progress:
            progress_map.setdefault(item.case_id, []).append(item)

        result = [
            {
                "case_id": str(case.id),
                "product_id": case.product_id,
                "policy_no": case.policy_no,
                "incident_type": case.incident_type,
                "incident_description": case.incident_description,
                "incident_date": case.incident_date,
                "claim_amount": case.claim_amount,
                "status": case.status,
                "progress": [
                    {
                        "node": p.node,
                        "status": p.status,
                        "remark": p.remark,
                    }
                    for p in progress_map.get(case.id, [])
                ],
            }
            for case in cases
        ]
        return json.dumps(result, ensure_ascii=False, default=str)
