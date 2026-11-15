from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.agents.tools import query_candidate_products,save_insurance_plan,query_product_clause
from app.modules.insurance_plan.schemas import InsuranceAgentContext
from app.core.config import settings
from app.core.logging import get_logger
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
你是“安心保”的智能保险顾问。
- 你需要使用专业、准确、容易理解的语言回答用户的保险问题。
- 当信息不足时，应先向用户追问，形成用户画像。
- 给用户推荐保险方案时，必须先查询候选产品，根据用户画像，推荐合适的保险组合，再调用工具保存方案。
- 回答保险产品的条款问题时，必须先调用query_product_clause查询对应产品的保险条款，再根据检索结果回答。
- 你的回答必须是基于检索到的保险条款，不要编造保险条款中没有的信息。如果没有相关条款，如实告知用户。
- 回答要简短、精确，不要长篇大论。
"""

async def init_insurance_agent(checkpointer: AsyncPostgresSaver):
    """初始化保险顾问Agent"""

    # 1.初始化模型
    model = init_chat_model(
        model=settings.llm.chat_model,
        model_provider="deepseek",
        api_key=settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}},
    )

    # 2.创建Agent
    agent = create_agent(
        model=model,
        tools=[query_candidate_products,save_insurance_plan,query_product_clause],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        context_schema=InsuranceAgentContext,  # Context约束
        middleware=[ToolErrorMiddleware(on_error=handle_tool_error)],
    )
    logger.info("保险顾问Agent初始化成功~✅️")
    return agent