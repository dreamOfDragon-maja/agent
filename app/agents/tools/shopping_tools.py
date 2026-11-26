import json
from decimal import Decimal

from langchain.tools import tool
from langgraph.config import get_stream_writer
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.modules.product.schemas import ProductResponse
from app.modules.product.service import ProductService
from app.modules.shopping_plan.schemas import (
    ShoppingAgentContext,
    ShoppingPlanCreate,
)
from app.modules.shopping_plan.service import ShoppingPlanService


@tool
async def query_candidate_products(
    categories: list[str],
    max_price: Decimal | None = None,
    limit_per_category: int = 5,
):
    """
    根据商品分类和预算查询可用于推荐的商品。当用户咨询具体商品、对比商品或需要选购建议时使用。

    Args:
        categories: 商品分类列表，可选值为 digital(数码影音)、appliance(家用电器)、beauty(美妆个护)、maternal(母婴亲子)。
        max_price: 预算上限，可选参数，只返回最低价不高于该值的商品。
        limit_per_category: 每个分类最多返回的商品数量，可选参数，默认5。
    """

    async with AsyncSessionFactory() as session:
        service = ProductService(session)
        products: list[Product] = await service.list_candidates(
            categories,
            max_price,
            limit_per_category,
        )
        product_cards = [
            ProductResponse.model_validate(product).model_dump(mode="json")
            for product in products
        ]

    # 把候选商品写入自定义事件，前端据此展示商品卡片
    writer = get_stream_writer()
    writer(
        {
            "type": "additional_info",
            "data": {
                "title": "推荐商品",
                "candidate_products": product_cards,
            },
        }
    )
    return json.dumps(product_cards, ensure_ascii=False)


@tool
async def save_shopping_plan(
    plan: ShoppingPlanCreate,
    runtime: ToolRuntime[ShoppingAgentContext],
) -> dict[str, str]:
    """请用户确认后，保存当前商品推荐/搭配方案。"""

    decision = interrupt(
        {
            "plan": plan.model_dump(mode="json"),
            "confirm_info": "是否确认保存这份购物方案？",
            "action": ["approve", "reject"],
        }
    )
    if decision.get("action") != "approve":
        return {
            "message": f"用户取消保存购物方案, 原因:{decision.get('reject_reason')}"
        }

    async with AsyncSessionFactory() as session:
        service = ShoppingPlanService(session)
        plan_id = await service.create_plan(
            user_id=runtime.context.user_id,
            data=plan,
        )
        saved_plan = await service.get_plan(runtime.context.user_id, plan_id)

    # 保存成功后下发带 plan_id/item_id 的卡片，前端可以继续下单
    plan_items = [
        {
            "id": str(item.id),
            "plan_id": str(saved_plan.id),
            "product_id": item.product_id,
            "name": item.product_name,
            "category": item.category,
            "brand": item.brand,
            "image_url": item.image_url,
            "unit_price": str(item.unit_price) if item.unit_price is not None else None,
            "recommendation_reason": item.recommendation_reason,
            "status": item.status,
        }
        for item in saved_plan.items
    ]
    writer = get_stream_writer()
    writer(
        {
            "type": "additional_info",
            "data": {
                "title": "已保存的购物方案",
                "plan_items": plan_items,
            },
        }
    )

    return {
        "plan_id": str(plan_id),
        "message": "购物方案保存成功",
    }


@tool
async def query_product_knowledge(
    query: str,
    k: int,
    product_name: str | None = None,
    product_id: int | None = None,
) -> str:
    """查询指定商品的说明书、保修和退换货政策。

    优先传入 product_name（用户提到的商品名称）；只有在已知有效商品ID时才传 product_id。
    不要猜测或传 product_id=0。

    Args:
        query: 需要从商品资料中查询的问题。
        k: 返回的文档数量。
        product_name: 商品名称，例如“星驰 X1 无线降噪耳机”。
        product_id: 商品ID，可选；不确定时留空并传 product_name。
    """
    from app.rag import retriever
    from app.modules.product.repository import ProductRepository

    resolved_id: int | None = None
    resolved_name: str | None = None

    async with AsyncSessionFactory() as session:
        repository = ProductRepository(session)
        if product_id is not None and product_id > 0:
            products = await repository.find_by_ids([product_id])
            if not products:
                return f"没有找到商品 ID {product_id}，请确认商品信息。"
            resolved_id = products[0].id
            resolved_name = products[0].name
        elif product_name and product_name.strip():
            matches = await repository.search_by_name(product_name.strip())
            if not matches:
                return f"没有找到名称包含“{product_name}”的商品，请确认商品名称。"
            resolved_id = matches[0].id
            resolved_name = matches[0].name
        else:
            return "请提供商品名称或有效的商品 ID，我再帮您查询。"

    chunks = await retriever.retrieve(query, k, resolved_id)
    if not chunks:
        return f"没有查询到“{resolved_name}”的相关商品资料。"

    sources = {
        f"ref-{i:03d}": {
            "product_id": chunk.product_id,
            "product_name": resolved_name,
            "document_name": chunk.document_name,
            "section_path": chunk.section_path,
            "content": chunk.content,
        }
        for i, chunk in enumerate(chunks, start=1)
    }

    writer = get_stream_writer()
    writer({"type": "additional_info", "data": {"sources": sources}})
    return json.dumps(sources, ensure_ascii=False)
