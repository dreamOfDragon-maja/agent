"""按 ORM 模型创建商城业务表。

生产环境建议使用 deploy/postgres/init 下的 SQL 初始化脚本；
本脚本用于已有数据库补齐缺失表，或在本地快速建表。
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.common.models import Base
from app.infra.database import engine

# 导入业务模型，确保 Base.metadata 中的外键都能解析。
# parent_chunks 由 deploy/postgres/init/02-init-agent-schema.sql 创建，
# 这里不导入 app.rag，避免仅建业务表时初始化 Milvus 客户端。
from app.modules.user.models import User  # noqa: F401
from app.modules.product.models import Product  # noqa: F401
from app.modules.shopping_plan.models import ShoppingPlan, ShoppingPlanItem  # noqa: F401
from app.modules.order.models import ShopOrder  # noqa: F401
from app.modules.after_sales.models import AfterSalesTicket, AfterSalesProgress  # noqa: F401
from app.modules.chat_thread.models import ChatThread  # noqa: F401


async def create_tables() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 商城业务表创建/校验完成")
    except Exception as exc:
        print(f"❌ 建表失败: {exc}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
