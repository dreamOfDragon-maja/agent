# ShopMate Agent Service

优选智购后端：FastAPI + LangGraph + PostgreSQL + Milvus。

## 模块

```text
app/
  main.py                 应用入口、生命周期、路由注册
  core/
    config.py             Pydantic Settings
    security.py           JWT / Argon2 / 当前用户依赖
  modules/
    auth/                 登录与当前用户
    product/              商品目录
    shopping_plan/        购物方案
    order/                订单
    after_sales/          售后工单与进度
    chat/                 SSE 对话流
    chat_thread/          会话管理与历史
    user/                 用户模型
  agents/
    orchestrator.py       主图：route → recommendation / after_sales / chitchat
    intent_router.py      意图识别 + 规则寒暄
    shopping_advisor.py   购物顾问 Agent
    after_sales.py        售后顾问 Agent
    tools/                商品查询、方案保存、知识检索、订单/售后工具
  rag/
    pipeline.py           Markdown/PDF 解析、父子块切分、入库
    retriever.py          Milvus 混合检索 + 父块回表
```

## 启动

```bash
cp .env.example .env
# 填入 DEEPSEEK_API_KEY，设置 JWT_SECRET
uv sync
uv run python app/main.py
```

默认 `http://127.0.0.1:8001`。

初始化：

```bash
uv run python scripts/init_db.py      # 按 ORM 模型补齐业务表
uv run python scripts/ingest_rag.py   # 构建商品知识库
```

## 旧库迁移

如果 `.env` 指向的数据库仍是旧保险结构（`products` 里是 `clause_name / insurer / min_premium / max_premium`），先预览再迁移：

```bash
uv run python scripts/migrate_legacy_db.py --dry-run
uv run python scripts/migrate_legacy_db.py
```

脚本会：

- 备份 `products` / `users` 到 `_backup_products_20261126` / `_backup_users_20261126`
- 重命名 `products`、`parent_chunks` 的旧字段
- 把 12 条演示商品替换为优选智购商品
- 重置 demo 账号密码并补齐订单/售后种子数据
- 不删除旧保险业务表

迁移后再执行 `uv run python scripts/ingest_rag.py`。

## 环境变量

见 [`.env.example`](.env.example)。关键项：

- `DEEPSEEK_API_KEY`：对话与意图识别
- `DB_*`：PostgreSQL，默认 `shopmate`
- `MILVUS_HOST` / `MILVUS_PORT` / `RAG_COLLECTION`：向量库
- `JWT_SECRET`：生产必须替换为随机长字符串
- `MINERU_TOKEN`：仅导入 PDF 知识文档时需要

## 自测

```bash
.venv/Scripts/python.exe -m compileall -q app scripts
.venv/Scripts/python.exe scripts/smoke_checks.py
```

`smoke_checks.py` 不依赖数据库和 Milvus，覆盖密码/JWT、订单号、意图规则、路由注册、知识文档与切分。

## Agent 流程

```text
START → route
      ├─ recommendation（购物顾问）
      ├─ after_sales（售后顾问）
      ├─ chitchat
      ├─ human_handoff
      └─ fallback
```

- 购物顾问：`query_candidate_products` → `save_shopping_plan`（interrupt 确认）→ `query_product_knowledge`（引用）
- 售后顾问：`query_user_orders` → `query_product_knowledge` → `create_after_sales_ticket`（interrupt 确认）→ `query_after_sales_progress`
- 会话状态由 `AsyncPostgresSaver` 持久化；前端通过 SSE 接收 `message` / `additional_info` / `interrupt` / `error` 事件。

## 知识库

`data/raw/kb/*.md` 为演示商品说明书，包含商品概述、使用说明、保修政策、退换货政策和常见问题。重新生成：

```bash
python scripts/generate_product_docs.py
uv run python scripts/ingest_rag.py
```

导入 PDF 时，`RAGPipeline` 会按需初始化 MinerU，并用模型修正 Markdown 结构；Markdown/TXT 直接读取，不依赖 MinerU。
