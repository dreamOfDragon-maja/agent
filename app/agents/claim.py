from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain.chat_models import init_chat_model

from app.agents.tools.claim_tools import create_claim_report, query_claim_progress
from app.agents.insurance_advisor import handle_tool_error
from app.agents.tools.insurance_advisor_tool import query_product_clause
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.insurance_plan.schemas import InsuranceAgentContext

logger = get_logger(__name__)

CLAIM_SYSTEM_PROMPT = """
你是"安心保"的理赔服务顾问。

- 使用专业、准确、容易理解的语言回答用户的理赔问题。

- 回答理赔责任、理赔材料、理赔流程等问题时，必须先调用 query_product_clause 查询对应产品的保险条款，再根据检索到的"理赔"相关章节回答，不要编造条款中没有的信息。

- 用户要求报案时，需要先收集齐全：出险产品、出险类型（疾病/意外）、出险时间、出险经过，以及可选信息（申请理赔金额、保单号），然后调用 create_claim_report 提交报案，经用户确认后才真正创建案件。

- 用户查询理赔进度时，调用 query_claim_progress 查询该用户的理赔案件与进度。

- 回答中的每个事实陈述必须紧跟 [source_id] 的引用标记。例如：意外医疗无等待期。[ref-001]

- 回答要简短、精确，不要长篇大论。

- 涉及身份证号、银行卡号等敏感信息时，不要主动索要，也不要复述完整号码。
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
        tools=[query_product_clause, create_claim_report, query_claim_progress],
        system_prompt=CLAIM_SYSTEM_PROMPT,
        checkpointer=True,
        context_schema=InsuranceAgentContext,
        middleware=[ToolErrorMiddleware(on_error=handle_tool_error)],
    )
    logger.info("理赔顾问Agent初始化成功~✅️")
    return agent
