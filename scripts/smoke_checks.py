"""不依赖数据库/向量库的冒烟检查。

运行：
    .venv/Scripts/python.exe scripts/smoke_checks.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.intent_router import match_social_intent  # noqa: E402
from app.core.security import create_access_token, decode_access_token, verify_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.order.service import OrderService  # noqa: E402
from app.modules.product.models import Product  # noqa: E402
from app.rag.pipeline import RAGPipeline  # noqa: E402


def check_security() -> None:
    demo_hash = (
        "$argon2id$v=19$m=65536,t=3,p=4$m+El37kDwbt9PPb5kiMr7g$"
        "v33ErFPCccmZqFesNi+CpJlWvbs4E/VZFEDygt/sVbQ"
    )
    assert verify_password("ShopMate@2026", demo_hash)
    assert not verify_password("wrong-password", demo_hash)
    token, expires_in = create_access_token(1)
    assert decode_access_token(token) == 1
    assert expires_in > 0


def check_order_number() -> None:
    number = OrderService._new_order_number()
    assert number.startswith("SM")
    assert len(number) > 10


def check_intent_rules() -> None:
    assert match_social_intent("你好") == "greeting"
    assert match_social_intent("谢谢") == "thanks"
    assert match_social_intent("再见") == "goodbye"


def check_routes() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/auth/login",
        "/api/v1/products",
        "/api/v1/shopping-plans/{plan_id}",
        "/api/v1/orders",
        "/api/v1/orders/{order_id}/pay",
        "/api/v1/chat",
        "/api/v1/chat-threads",
    }
    missing = expected.difference(paths)
    assert not missing, f"missing routes: {missing}"


def check_knowledge_docs() -> None:
    kb = PROJECT_ROOT / "data" / "raw" / "kb"
    docs = sorted(kb.glob("*.md"))
    assert len(docs) == 12, f"expected 12 docs, got {len(docs)}"
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for section in ("## 商品概述", "## 保修政策", "## 退换货政策"):
            assert section in text, f"{doc.name} missing {section}"

    pipeline = RAGPipeline(None)  # 只测试解析/切分，不连接向量库
    product = Product(
        id=1,
        name="星驰 X1 无线降噪耳机",
        document_name="星驰X1无线降噪耳机使用说明书.md",
    )
    markdown = pipeline._parse_and_optimize(product.document_name)
    parents, children = pipeline._chunk(markdown, product)
    assert parents and children
    assert all(parent.document_name == product.document_name for parent in parents)


def main() -> None:
    check_security()
    check_order_number()
    check_intent_rules()
    check_routes()
    check_knowledge_docs()
    print("✅ smoke checks passed")


if __name__ == "__main__":
    main()
