import json

from langchain.tools import tool
from langgraph.config import get_stream_writer
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from app.infra.database import AsyncSessionFactory
from app.modules.after_sales.schemas import AfterSalesTicketCreate
from app.modules.after_sales.service import AfterSalesService
from app.modules.order.service import OrderService
from app.modules.shopping_plan.schemas import ShoppingAgentContext


@tool
async def query_user_orders(
    runtime: ToolRuntime[ShoppingAgentContext],
) -> str:
    """查询当前用户的订单，包括订单 ID、订单号、商品、金额、状态和下单时间。处理售后前必须先调用此工具，确认用户要处理哪一笔订单。"""
    async with AsyncSessionFactory() as session:
        service = OrderService(session)
        orders = await service.list_orders(runtime.context.user_id)
        order_cards = [order.model_dump(mode="json") for order in orders]

    writer = get_stream_writer()
    writer(
        {
            "type": "additional_info",
            "data": {
                "title": "我的订单",
                "orders": order_cards,
            },
        }
    )
    if not order_cards:
        return "当前暂无订单。"
    return json.dumps(order_cards, ensure_ascii=False)


@tool
async def create_after_sales_ticket(
    ticket: AfterSalesTicketCreate,
    runtime: ToolRuntime[ShoppingAgentContext],
) -> dict[str, str]:
    """用户确认问题信息后，提交售后申请。提交前必须已收集齐全订单、问题类型、问题经过和期望处理方式。"""

    decision = interrupt(
        {
            "ticket": ticket.model_dump(mode="json"),
            "confirm_info": "是否确认提交本次售后申请？",
            "action": ["approve", "reject"],
        }
    )
    if decision.get("action") != "approve":
        return {
            "message": f"用户取消售后申请, 原因:{decision.get('reject_reason')}"
        }

    async with AsyncSessionFactory() as session:
        service = AfterSalesService(session)
        ticket_id = await service.create_ticket(
            user_id=runtime.context.user_id,
            data=ticket,
        )

    return {
        "ticket_id": str(ticket_id),
        "message": "售后申请提交成功",
    }


@tool
async def query_after_sales_progress(
    runtime: ToolRuntime[ShoppingAgentContext],
) -> str:
    """查询当前用户的售后工单及其处理进度。"""

    async with AsyncSessionFactory() as session:
        service = AfterSalesService(session)
        tickets = await service.list_by_user(runtime.context.user_id)
        if not tickets:
            return "当前暂无售后记录。"

        progress = await service.list_progress([ticket.id for ticket in tickets])
        progress_map: dict = {}
        for item in progress:
            progress_map.setdefault(item.ticket_id, []).append(item)

        result = [
            {
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "order_id": str(ticket.order_id),
                "product_id": ticket.product_id,
                "issue_type": ticket.issue_type,
                "issue_description": ticket.issue_description,
                "desired_resolution": ticket.desired_resolution,
                "status": ticket.status,
                "progress": [
                    {
                        "node": item.node,
                        "status": item.status,
                        "remark": item.remark,
                    }
                    for item in progress_map.get(ticket.id, [])
                ],
            }
            for ticket in tickets
        ]
        return json.dumps(result, ensure_ascii=False, default=str)
