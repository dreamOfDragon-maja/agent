"""把旧的保险演示库原地迁移为优选智购结构。

适用场景：
- 数据库里已经有旧的 products / parent_chunks 表；
- 新表 shopping_plans / shop_orders / after_sales_* 已由 init_db.py 创建；
- 不想重建整个数据库。

原则：
- 不删除旧表；
- 迁移前备份 products 和 users；
- 只重命名列、替换 12 条演示商品、更新演示账号、补齐 seed 数据；
- 可重复执行。
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

from app.core.config import settings
from app.core.security import hash_password

DEMO_PASSWORD = "ShopMate@2026"

PRODUCTS = [
    (1, "星驰 X1 无线降噪耳机", "星驰X1无线降噪耳机使用说明书.md", "digital", "星驰",
     "40mm 动圈单元与自适应降噪，适合通勤、办公和长时间佩戴。", 699.00, 899.00,
     "通勤/办公/学生", ["主动降噪", "40小时续航", "双设备连接"]),
    (2, "锐影 4K 运动相机", "锐影4K运动相机使用说明书.md", "digital", "锐影",
     "轻量机身与电子防抖，记录旅行、运动和日常 Vlog。", 1299.00, 1599.00,
     "旅行/运动/Vlog", ["4K/60fps", "六轴防抖", "30米防水"]),
    (3, "声阔 Mini 蓝牙音箱", "声阔Mini蓝牙音箱使用说明书.md", "digital", "声阔",
     "小巧便携的户外音箱，支持双机串联和防水。", 249.00, 299.00,
     "居家/露营/学生", ["IPX7防水", "12小时续航", "双机互联"]),
    (4, "净界 A3 空气净化器", "净界A3空气净化器使用说明书.md", "appliance", "净界",
     "高效过滤颗粒物与甲醛，适合新居和母婴家庭。", 1299.00, 1699.00,
     "新居/母婴/过敏人群", ["除甲醛", "静音睡眠模式", "滤芯提醒"]),
    (5, "悦光 S2 智能护眼台灯", "悦光S2智能护眼台灯使用说明书.md", "appliance", "悦光",
     "全光谱灯珠与自动调光，减少长时间阅读的视觉疲劳。", 299.00, 399.00,
     "学生/办公/阅读", ["无频闪", "自动调光", "定时休息"]),
    (6, "静风 变频落地扇", "静风变频落地扇使用说明书.md", "appliance", "静风",
     "直流变频电机，风感柔和，夜间运行更安静。", 399.00, 499.00,
     "卧室/客厅/办公", ["直流变频", "12档风速", "遥控定时"]),
    (7, "沁润 玻尿酸保湿精华", "沁润玻尿酸保湿精华使用说明书.md", "beauty", "沁润",
     "多重保湿成分，改善干燥紧绷，敏感肌可用。", 199.00, 259.00,
     "干性/敏感肌", ["5重玻尿酸", "敏感肌适用", "清爽不黏腻"]),
    (8, "轻岚 氨基酸洁面乳", "轻岚氨基酸洁面乳使用说明书.md", "beauty", "轻岚",
     "氨基酸表活温和清洁，洗后不紧绷。", 89.00, 119.00,
     "所有肤质/学生", ["温和清洁", "不紧绷", "泡沫细腻"]),
    (9, "净享 便携冲牙器", "净享便携冲牙器使用说明书.md", "beauty", "净享",
     "高频脉冲水流清洁牙缝，适合正畸和日常口腔护理。", 199.00, 249.00,
     "正畸/口腔护理", ["3档模式", "IPX7防水", "长续航"]),
    (10, "柔护 婴儿纸尿裤 L码", "柔护婴儿纸尿裤使用说明书.md", "maternal", "柔护",
     "轻薄透气芯体，弱酸性表层，适合宝宝日常使用。", 129.00, 159.00,
     "6-11kg 宝宝", ["轻薄透气", "弱酸性", "尿显设计"]),
    (11, "童趣 儿童安全座椅", "童趣儿童安全座椅使用说明书.md", "maternal", "童趣",
     "ISOFIX 硬接口与侧面防护，覆盖 0-7 岁。", 1599.00, 1999.00,
     "0-7岁儿童", ["ISOFIX", "侧面防护", "可调节头枕"]),
    (12, "暖绒 婴儿连体衣", "暖绒婴儿连体衣使用说明书.md", "maternal", "暖绒",
     "A 类纯棉面料，无骨缝制，贴身穿着更舒适。", 99.00, 129.00,
     "0-2岁宝宝", ["A类纯棉", "无骨缝制", "四季款"]),
]


async def column_exists(conn: asyncpg.Connection, table: str, column: str) -> bool:
    return await conn.fetchval(
        """
        select exists(
            select 1 from information_schema.columns
            where table_schema = 'public' and table_name = $1 and column_name = $2
        )
        """,
        table,
        column,
    )


async def constraint_exists(conn: asyncpg.Connection, table: str, name: str) -> bool:
    return await conn.fetchval(
        """
        select exists(
            select 1
            from pg_constraint con
            join pg_class rel on rel.oid = con.conrelid
            where rel.relname = $1 and con.conname = $2
        )
        """,
        table,
        name,
    )


async def rename_column(conn: asyncpg.Connection, table: str, old: str, new: str) -> None:
    if await column_exists(conn, table, old) and not await column_exists(conn, table, new):
        await conn.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"')
        print(f"renamed {table}.{old} -> {new}")


async def add_constraint(conn: asyncpg.Connection, table: str, name: str, definition: str) -> None:
    if not await constraint_exists(conn, table, name):
        await conn.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" {definition}')
        print(f"added constraint {name}")


async def migrate_products(conn: asyncpg.Connection) -> None:
    await rename_column(conn, "products", "clause_name", "document_name")
    await rename_column(conn, "products", "insurer", "brand")
    await rename_column(conn, "products", "min_premium", "min_price")
    await rename_column(conn, "products", "max_premium", "max_price")

    # 旧的分类约束只允许保险分类，先移除，更新完商品后再加新约束
    await conn.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS chk_products_category")

    rows = [
        (
            pid, name, doc, category, brand, description,
            min_price, max_price, target, highlights,
        )
        for pid, name, doc, category, brand, description, min_price, max_price, target, highlights in PRODUCTS
    ]
    await conn.executemany(
        """
        UPDATE products
        SET name = $2,
            document_name = $3,
            category = $4,
            brand = $5,
            image_url = NULL,
            description = $6,
            min_price = $7,
            max_price = $8,
            target_group = $9,
            highlights = $10,
            status = 'active',
            updated_at = NOW()
        WHERE id = $1
        """,
        rows,
    )
    print(f"updated {len(rows)} products")

    await add_constraint(
        conn,
        "products",
        "chk_products_category",
        "CHECK (category IN ('digital', 'appliance', 'beauty', 'maternal'))",
    )


async def migrate_parent_chunks(conn: asyncpg.Connection) -> None:
    await rename_column(conn, "parent_chunks", "clause_name", "document_name")


async def migrate_user(conn: asyncpg.Connection) -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    exists = await conn.fetchval("select exists(select 1 from users where id = 1)")
    if exists:
        await conn.execute(
            """
            UPDATE users
            SET username = 'demo',
                email = 'demo@shopmate.example',
                password_hash = $1,
                display_name = '演示用户',
                status = 'active',
                updated_at = NOW()
            WHERE id = 1
            """,
            password_hash,
        )
    else:
        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, display_name, status)
            VALUES (1, 'demo', 'demo@shopmate.example', $1, '演示用户', 'active')
            """,
            password_hash,
        )
    print("updated demo user password")


async def ensure_new_table_constraints(conn: asyncpg.Connection) -> None:
    await add_constraint(
        conn, "shopping_plans", "chk_shopping_plans_budget",
        "CHECK (total_budget IS NULL OR total_budget >= 0)",
    )
    await add_constraint(
        conn, "shopping_plans", "chk_shopping_plans_status",
        "CHECK (status IN ('active', 'ordered', 'completed'))",
    )
    await add_constraint(
        conn, "shopping_plan_items", "chk_shopping_plan_items_price",
        "CHECK (unit_price IS NULL OR unit_price >= 0)",
    )
    await add_constraint(
        conn, "shopping_plan_items", "chk_shopping_plan_items_status",
        "CHECK (status IN ('pending', 'ordered', 'fulfilled'))",
    )
    await add_constraint(
        conn, "shopping_plan_items", "uk_shopping_plan_items_plan_product",
        "UNIQUE (plan_id, product_id)",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_quantity",
        "CHECK (quantity > 0)",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_price",
        "CHECK (unit_price >= 0)",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_total",
        "CHECK (total_amount >= 0)",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_status",
        "CHECK (status IN ('pending_payment', 'paid', 'shipped', 'completed', 'cancelled'))",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_delivery",
        "CHECK (delivery_method IN ('standard', 'express'))",
    )
    await add_constraint(
        conn, "shop_orders", "chk_shop_orders_invoice",
        "CHECK (invoice_type IN ('none', 'personal', 'company'))",
    )
    await add_constraint(
        conn, "after_sales_tickets", "chk_after_sales_issue_type",
        "CHECK (issue_type IN ('return', 'exchange', 'repair', 'refund', 'other'))",
    )
    await add_constraint(
        conn, "after_sales_tickets", "chk_after_sales_status",
        "CHECK (status IN ('submitted', 'reviewing', 'approved', 'rejected', 'completed'))",
    )


async def seed_orders_and_tickets(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO shop_orders (
            id, user_id, order_number, plan_id, plan_item_id, product_id,
            quantity, unit_price, total_amount, status, shipping_info,
            payment_method, delivery_method, invoice_type, paid_at,
            created_at, updated_at
        )
        VALUES
        (
            '30000000-0000-0000-0000-000000000001', 1, 'SM-DEMO-2026-0001',
            NULL, NULL, 1, 1, 699.00, 699.00, 'paid', $1::jsonb,
            'online', 'standard', 'none',
            CURRENT_TIMESTAMP - INTERVAL '5 days',
            CURRENT_TIMESTAMP - INTERVAL '5 days',
            CURRENT_TIMESTAMP - INTERVAL '5 days'
        ),
        (
            '30000000-0000-0000-0000-000000000002', 1, 'SM-DEMO-2026-0002',
            NULL, NULL, 10, 1, 129.00, 129.00, 'completed', $1::jsonb,
            'online', 'standard', 'none',
            CURRENT_TIMESTAMP - INTERVAL '60 days',
            CURRENT_TIMESTAMP - INTERVAL '60 days',
            CURRENT_TIMESTAMP - INTERVAL '60 days'
        )
        ON CONFLICT (id) DO NOTHING
        """,
        json.dumps(
            {
                "recipient_name": "演示用户",
                "phone": "13800000000",
                "address": "上海市浦东新区示例路 88 号",
                "note": None,
            },
            ensure_ascii=False,
        ),
    )
    await conn.execute(
        """
        INSERT INTO after_sales_tickets (
            id, user_id, order_id, product_id, ticket_number, issue_type,
            issue_description, desired_resolution, status, created_at, updated_at
        )
        VALUES (
            '40000000-0000-0000-0000-000000000001', 1,
            '30000000-0000-0000-0000-000000000001', 1,
            'AS-DEMO-2026-0001', 'exchange',
            '耳机右耳在连接后偶发断连，已尝试重置仍无法解决。',
            '希望更换同型号新品', 'reviewing',
            CURRENT_TIMESTAMP - INTERVAL '2 days',
            CURRENT_TIMESTAMP - INTERVAL '1 day'
        )
        ON CONFLICT (id) DO NOTHING
        """
    )
    await conn.execute(
        """
        INSERT INTO after_sales_progress (id, ticket_id, node, status, remark, created_at)
        VALUES
        (
            '50000000-0000-0000-0000-000000000001',
            '40000000-0000-0000-0000-000000000001',
            '提交申请', 'done', '售后申请提交成功',
            CURRENT_TIMESTAMP - INTERVAL '2 days'
        ),
        (
            '50000000-0000-0000-0000-000000000002',
            '40000000-0000-0000-0000-000000000001',
            '审核处理', 'processing', NULL,
            CURRENT_TIMESTAMP - INTERVAL '1 day'
        )
        ON CONFLICT (id) DO NOTHING
        """
    )
    print("seeded demo orders and after-sales ticket")


async def preview(conn: asyncpg.Connection) -> None:
    """只读预览：展示将要做出的结构/数据变更，不修改数据库。"""

    db_name = await conn.fetchval("select current_database()")
    print(f"target database: {settings.db.host}:{settings.db.port}/{db_name}")
    print(f"db user: {settings.db.user}")

    product_columns = [
        row["column_name"]
        for row in await conn.fetch(
            """
            select column_name from information_schema.columns
            where table_schema = 'public' and table_name = 'products'
            order by ordinal_position
            """
        )
    ]
    print("products columns:", product_columns)
    renames = []
    for old, new in [
        ("clause_name", "document_name"),
        ("insurer", "brand"),
        ("min_premium", "min_price"),
        ("max_premium", "max_price"),
    ]:
        if old in product_columns and new not in product_columns:
            renames.append(f"{old} -> {new}")
    print("planned column renames:", renames or "none")

    categories = await conn.fetch(
        "select category, count(*) as count from products group by category order by category"
    )
    print("current product categories:", [dict(row) for row in categories])
    print("products rows:", await conn.fetchval("select count(*) from products"))

    parent_columns = [
        row["column_name"]
        for row in await conn.fetch(
            """
            select column_name from information_schema.columns
            where table_schema = 'public' and table_name = 'parent_chunks'
            order by ordinal_position
            """
        )
    ]
    print("parent_chunks columns:", parent_columns)
    if "clause_name" in parent_columns and "document_name" not in parent_columns:
        print("planned parent_chunks rename: clause_name -> document_name")

    demo = await conn.fetchrow(
        "select id, username, password_hash from users where id = 1"
    )
    if demo is None:
        print("planned demo user: insert id=1 username=demo")
    else:
        from app.core.security import verify_password

        print(
            "demo user:",
            {"id": demo["id"], "username": demo["username"]},
            "password already matches:",
            verify_password(DEMO_PASSWORD, demo["password_hash"]),
        )
        print("planned demo user: reset password to demo password if not matching")

    for table in (
        "shopping_plans",
        "shopping_plan_items",
        "shop_orders",
        "after_sales_tickets",
        "after_sales_progress",
    ):
        exists = await conn.fetchval(
            "select exists(select 1 from information_schema.tables where table_schema='public' and table_name=$1)",
            table,
        )
        count = await conn.fetchval(f'select count(*) from "{table}"') if exists else None
        print(f"{table}: exists={exists}, rows={count}")

    print("planned seed: 2 demo orders + 1 after-sales ticket (only if ids are absent)")
    print("dry-run only: no changes were made")


async def main(dry_run: bool = False) -> None:
    conn = await asyncpg.connect(
        host=settings.db.host,
        port=settings.db.port,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.name,
    )
    try:
        if dry_run:
            await preview(conn)
            return

        async with conn.transaction():
            # 备份旧数据，重复执行时不会覆盖第一次的备份
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS _backup_products_20261126 AS SELECT * FROM products"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS _backup_users_20261126 AS SELECT * FROM users"
            )
            print("backup tables created: _backup_products_20261126, _backup_users_20261126")

            await migrate_products(conn)
            await migrate_parent_chunks(conn)
            await migrate_user(conn)
            await ensure_new_table_constraints(conn)
            await seed_orders_and_tickets(conn)
        print("✅ legacy database migration completed")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate legacy insurance demo DB to ShopMate schema")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only print planned changes; do not modify the database",
    )
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
