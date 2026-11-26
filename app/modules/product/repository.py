import re

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Product
from decimal import Decimal

class ProductRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def query_by_category(
        self,
        category: str | None = None,
    ) -> list[Product]:
        # 1.组装查询条件
        # 1.1.默认只查询active状态的产品
        conditions = [Product.status == "active"]
        # 1.2.如果有category，则添加category过滤
        if category:
            conditions.append(Product.category == category)

        # 2.查询产品列表
        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.id.asc())
        )
        return products.all()

    async def find_limited_by_category(
            self,
            category: str,
            max_price: Decimal | None,
            limit: int,
    ) -> list[Product]:
        conditions = [
            Product.status == "active",
            Product.category == category,
        ]
        if max_price is not None:
            conditions.append(Product.min_price <= max_price)

        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(
                Product.min_price.asc().nullslast(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        return products.all()

    async def find_by_ids(self, product_ids: list[int]) -> list[Product]:
        if not product_ids:
            return []
        products = await self.session.scalars(
            select(Product).where(Product.id.in_(product_ids))
        )
        return list(products.all())

    async def search_by_name(self, keyword: str, limit: int = 5) -> list[Product]:
        """按商品名称关键词搜索。

        以空格/标点拆词，每个词都必须在商品名称中出现（忽略名称中的空格），
        这样“星驰 X1 耳机”也能命中“星驰 X1 无线降噪耳机”。
        """

        tokens = [
            token
            for token in re.split(r"[\s,，。;；/]+", keyword.strip())
            if token
        ]
        if not tokens:
            return []

        conditions = [Product.status == "active"]
        for token in tokens:
            compact = token.replace(" ", "")
            conditions.append(
                or_(
                    Product.name.ilike(f"%{token}%"),
                    func.replace(Product.name, " ", "").ilike(f"%{compact}%"),
                )
            )

        products = await self.session.scalars(
            select(Product)
            .where(*conditions)
            .order_by(Product.id.asc())
            .limit(limit)
        )
        return list(products.all())