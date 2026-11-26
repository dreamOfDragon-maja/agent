from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .intent_router import intent_router
from app.agents.chitchat import init_chitchat_agent
from app.agents.shopping_advisor import init_shopping_advisor
from app.agents.after_sales import init_after_sales_agent

from app.agents.schemas import (
    ShoppingAgentState,
    Intent
)

# 一、定义节点

# 1.路由节点
async def route_node(
    state: ShoppingAgentState,
) -> Command[Intent]:
    """意图识别节点"""
    # 1.获取active_workflow，也就是上一轮会话的工作流
    previous_workflow = state.get("active_workflow", "")
    # 2.获取上轮AI消息
    previous_ai_message = find_previous_ai_message(state['messages'])
    # 3.拼接上下文
    context = f"上轮对话工作流:{previous_workflow}\n上轮对话AI回复:{previous_ai_message}"
    # 4.意图识别
    result = await intent_router.route(state['messages'][-1].content, context)

    # 4.1.返回str，说明是寒暄，直接返回固定回复，跳至END
    if isinstance(result, str):
        return Command(
            update={
                "messages": [AIMessage(content=result)],
                "previous_workflow": previous_workflow,
                "active_workflow": "chitchat",
            },
            goto=END,
        )

    # 4.2.返回RouteResult，记录上轮工作流、本轮工作流
    return Command(
        update={
            "previous_workflow": previous_workflow,
            "active_workflow": result.intent
        },
        goto=result.intent,
    )

def find_previous_ai_message(messages: list[BaseMessage]) -> str:
    """查找本轮用户消息之前最近一条可展示的AI回复"""

    for message in reversed(messages[:-1]):
        # 跳过非AIMessage
        if not isinstance(message, AIMessage):
            continue
        # 跳过工具消息
        if message.tool_calls:
            continue
        # 如果是正常AIMessage，直接返回
        if message.text:
            return message.text
    # 如果是空消息
    return ""


# 2.闲聊节点
async def chitchat_node(state: ShoppingAgentState) -> dict:
    return {"messages": [AIMessage("你好，今天想了解点什么？")]}


# 3.商品推荐节点（占位，实际使用子 Agent）
async def recommendation_node(state: ShoppingAgentState) -> dict:
    return {"messages": [AIMessage("商品推荐工作流暂未接入。")]}


# 4.售后节点（占位，实际使用子 Agent）
async def after_sales_node(state: ShoppingAgentState) -> dict:
    return {"messages": [AIMessage("售后工作流暂未接入。")]}


# 5.人工节点
def human_handoff_node(state: ShoppingAgentState) -> dict:
    return {"messages": [AIMessage("已记录转人工请求，后续可接入人工客服系统。")]}


# 6.fallback节点
def fallback_node(state: ShoppingAgentState) -> dict:
    return {"messages": [AIMessage("我还不能确定你的需求，请说明是想选购商品、咨询商品说明还是办理售后。")]}


# 二、定义主Graph
async def init_shopping_orchestrator(
        checkpointer: AsyncPostgresSaver,
):
    """初始化商城智能顾问主Graph"""

    builder = StateGraph(ShoppingAgentState)
    builder.add_node("route", route_node)
    builder.add_node("chitchat", init_chitchat_agent())
    builder.add_node("recommendation", await init_shopping_advisor())
    builder.add_node("after_sales", await init_after_sales_agent())
    builder.add_node("human_handoff", human_handoff_node)
    builder.add_node("fallback", fallback_node)

    builder.add_edge(START, "route")
    builder.add_edge("chitchat", END)
    builder.add_edge("recommendation", END)
    builder.add_edge("after_sales", END)
    builder.add_edge("human_handoff", END)
    builder.add_edge("fallback", END)

    return builder.compile(checkpointer=checkpointer)
