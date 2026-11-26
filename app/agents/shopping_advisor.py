from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain.chat_models import init_chat_model

from app.agents.tools.shopping_tools import (
    query_candidate_products,
    query_product_knowledge,
    save_shopping_plan,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.modules.shopping_plan.schemas import ShoppingAgentContext

logger = get_logger(__name__)


def handle_tool_error(exc: Exception, request: Any) -> str:
    """把工具异常转换成错误消息返回给模型，避免对话历史中出现没有结果的 tool_call。"""
    tool_name = request.tool_call.get("name", "unknown")
    logger.exception("工具执行失败", tool_name=tool_name, error=str(exc))
    return (
        f"工具 {tool_name} 执行失败（{type(exc).__name__}），"
        "请向用户说明当前无法完成该操作，稍后再试，不要重复调用该工具。"
    )


SYSTEM_PROMPT = """
你是“优选智购”的智能购物顾问。
- 始终使用简体中文回答，不要使用英文开场或中英混杂。
- 你需要使用专业、准确、容易理解的语言回答用户的商品问题。
- 当信息不足时，应先向用户追问，形成用户画像（预算、使用场景、偏好、收货/使用人群等）。
- 给用户推荐商品时，必须先调用 query_candidate_products 查询候选商品，根据用户画像推荐合适的商品组合，再调用 save_shopping_plan 保存方案。
- 回答商品说明书、保修或退换货政策问题时，必须先调用 query_product_knowledge 查询对应商品的资料，再根据检索结果回答。
- 调用 query_product_knowledge 时，如果用户用商品名称提问，请把商品名称作为 product_name 传入；不要猜测 product_id，也不要传 product_id=0。
- 你的回答必须基于检索到的商品资料，不要编造资料中没有的信息。如果没有相关资料，如实告知用户。
- 回答中的每个事实陈述必须紧跟[source_id]的引用标记。例如：该商品支持 7 天无理由退货。[ref-001]
- 不要承诺资料中没有的折扣、赠品、物流时效或绝对化效果。
- 回答要简短、精确，不要长篇大论。
"""


async def init_shopping_advisor():
    """初始化购物顾问 Agent"""

    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )

    agent = create_agent(
        model=model,
        tools=[
            query_candidate_products,
            save_shopping_plan,
            query_product_knowledge,
        ],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=True,
        context_schema=ShoppingAgentContext,
        middleware=[ToolErrorMiddleware(on_error=handle_tool_error)],
    )
    logger.info("购物顾问 Agent 初始化成功~✅️")
    return agent
