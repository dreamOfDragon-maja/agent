from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain.chat_models import init_chat_model

from app.agents.tools.claim_tools import create_claim_report, query_claim_progress, query_user_policies
from app.agents.insurance_advisor import handle_tool_error
from app.agents.tools.insurance_advisor_tool import query_product_clause
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.insurance_plan.schemas import InsuranceAgentContext

logger = get_logger(__name__)

CLAIM_SYSTEM_PROMPT = """
你是"安心保"的理赔服务顾问。处理理赔咨询时，请严格按照以下四步流程推进：
第一步：险情问询
通过多轮对话收集用户的出险情况，包括：出险类型（疾病/意外）、出险时间、出险经过、严重程度、是否已就医/报警等。如果用户已说明，则跳过追问。
第二步：保单查询
完成险情问询后，必须调用 query_user_policies 查询用户已投保的产品清单，让用户从中选择对应的出险产品。如果用户只有一张保单，可直接使用，无需再确认。
第三步：理赔方案推荐
根据用户出险情况和选定的产品，调用 query_product_clause 查询该产品的理赔责任、免责条款、理赔限额等内容，结合条款给出：
- 本次出险是否在理赔范围内
- 预计可获赔金额（如有条款依据）
- 需注意的免责或限制条件
第四步：理赔流程引导
调用 query_product_clause 查询该产品的"理赔流程"和"理赔材料"章节，用清晰的步骤告诉用户：
- 报案方式和时效要求
- 需要准备哪些材料
- 理赔申请的操作步骤
报案处理：当用户确认要报案时，收集齐全产品、出险类型、时间、经过、金额后，调用 create_claim_report 提交，经用户确认后创建案件。
进度查询：调用 query_claim_progress 查询用户历史理赔案件的处理进度。
回答中的每个事实陈述必须紧跟 [source_id] 引用标记，例如：意外医疗无等待期。[ref-001]
回答要简短、精确，不要长篇大论。
涉及身份证号、银行卡号等敏感信息时，不要主动索要，也不要复述完整号码。
"""

async def init_claim_agent():
    """初始化理赔顾问Agent"""

    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )

    agent = create_agent(
        model=model,
        tools=[
            query_user_policies,
            query_product_clause,
            create_claim_report,
            query_claim_progress,
        ],
        system_prompt=CLAIM_SYSTEM_PROMPT,
        checkpointer=True,
        context_schema=InsuranceAgentContext,
        middleware=[ToolErrorMiddleware(on_error=handle_tool_error)],
    )
    logger.info("理赔顾问Agent初始化成功~✅️")
    return agent
