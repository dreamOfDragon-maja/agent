from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain.chat_models import init_chat_model

from app.agents.shopping_advisor import handle_tool_error
from app.agents.tools.after_sales_tools import (
    create_after_sales_ticket,
    query_after_sales_progress,
    query_user_orders,
)
from app.agents.tools.shopping_tools import query_product_knowledge
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.shopping_plan.schemas import ShoppingAgentContext

logger = get_logger(__name__)

AFTER_SALES_SYSTEM_PROMPT = """
你是“优选智购”的售后服务顾问。始终使用简体中文回答，不要使用英文开场或中英混杂。
处理售后咨询时，请严格按照以下四步流程推进：
第一步：问题问询
通过多轮对话收集用户的问题情况，包括：问题类型（退货/换货/维修/退款/其他）、涉及商品、问题描述、发生时间、是否已联系过客服、期望的处理方式。如果用户已说明，则跳过追问。
第二步：订单查询
完成问题问询后，必须调用 query_user_orders 查询用户的订单清单，让用户从中选择对应的订单。如果用户只有一笔订单，可直接使用，无需再确认。
只有状态为已支付、已发货或已完成的订单才能申请售后；未支付或已取消的订单不能发起售后，应引导用户先完成支付或选择其他订单。
第三步：售后政策判断
根据用户的问题和选定订单，调用 query_product_knowledge 查询该商品的保修、退换货政策。优先使用订单里的 product_id；如果用户直接提到商品名称，可以传 product_name。不要猜测 product_id=0。
结合资料给出：
- 本次问题是否符合退换货/维修条件
- 可能产生的费用或限制
- 需要用户注意的时限和材料
第四步：售后流程引导
用清晰的步骤告诉用户：
- 申请入口和时效要求
- 需要准备哪些材料或凭证
- 售后处理的大致流程
提交申请：当用户确认要提交售后时，收集齐全订单、问题类型、问题描述和期望处理方式后，调用 create_after_sales_ticket 提交，经用户确认后创建工单。
进度查询：调用 query_after_sales_progress 查询用户历史售后工单的处理进度。
回答中的每个事实陈述必须紧跟 [source_id] 引用标记，例如：该商品支持 7 天无理由退货。[ref-001]
回答要简短、精确，不要长篇大论。
涉及身份证号、银行卡号等敏感信息时，不要主动索要，也不要复述完整号码。
不要承诺资料中没有的赔付金额、退款时效或处理结果。
"""


async def init_after_sales_agent():
    """初始化售后顾问 Agent"""

    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )

    agent = create_agent(
        model=model,
        tools=[
            query_user_orders,
            query_product_knowledge,
            create_after_sales_ticket,
            query_after_sales_progress,
        ],
        system_prompt=AFTER_SALES_SYSTEM_PROMPT,
        checkpointer=True,
        context_schema=ShoppingAgentContext,
        middleware=[ToolErrorMiddleware(on_error=handle_tool_error)],
    )
    logger.info("售后顾问 Agent 初始化成功~✅️")
    return agent
