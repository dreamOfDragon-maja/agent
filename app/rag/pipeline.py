from pathlib import Path
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from mineru import MinerU

from app.core.config import APP_ROOT, settings
from app.infra.database import AsyncSessionFactory
from app.modules.product.models import Product
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository
from app.core.logging import get_logger
logger = get_logger(__name__)


MARKDOWN_OPTIMIZATION_PROMPT = """
下面这份 Markdown 文档是从商品说明书/保修条款 PDF 解析得来，由于 PDF 中的各个小节是以表格形式存在，所以解析时出现错乱。你分析内容，帮我转为格式正确的 Markdown，特别是标题编号要正确。
- 标题等级要从 1 级标题开始，逐层增加，目录和文档名不计入标题等级。
- 输出结果中不要包含正文开始之前的部分。
- 输出结果只包含 Markdown 正文，不要解释或代码围栏。
- 不要修改商品说明、保修和退换货政策。
""".strip()


class RAGPipeline:

    def __init__(self, vector_store: Milvus) -> None:
        self._vector_store = vector_store

        # 1.文档解析工具按需初始化：Markdown/TXT 直接读取，只有 PDF 才需要 MinerU
        self._mineru: MinerU | None = None

        self._model = init_chat_model(
            settings.llm.chat_model,
            api_key=settings.llm.api_key,
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=10000,
        )

        # 2.初始化文档切分工具
        self._markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
                ("####", "h4"),
            ],
            strip_headers=True,
        )
        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", ";", "，", ","],
            keep_separator="end",
        )
        logger.info("RAG Pipeline 初始化完成✅️")

    async def ingest(self, product: Product) -> None:
        # 1.解析商品说明书/保修资料
        markdown = self._parse_and_optimize(product.document_name)

        # 2.切分父块和子块
        parent_chunks, child_chunks = self._chunk(markdown, product)

        # 3.子块存入Milvus
        self._save_child_chunks(product.id, child_chunks)

        # 4.父块存入PostgreSQL
        await self._save_parent_chunks(product.id, parent_chunks)

    def _parse_and_optimize(self, document_name: str) -> str:
        file_path = Path(APP_ROOT / "data" / "raw" / "kb" / document_name)
        if not file_path.exists():
            raise FileNotFoundError(f"商品知识文档不存在: {file_path}")

        # Markdown/TXT 直接读取，避免不必要的 PDF 解析和模型改写
        if file_path.suffix.lower() in {".md", ".markdown", ".txt"}:
            return file_path.read_text(encoding="utf-8")

        # PDF 使用 MinerU 解析，再让模型修正 Markdown 结构
        result = self._get_mineru().extract(str(file_path))
        response = self._model.invoke(
            [
                {"role": "system", "content": MARKDOWN_OPTIMIZATION_PROMPT},
                {"role": "user", "content": result.markdown},
            ]
        )
        return response.content

    def _get_mineru(self) -> MinerU:
        if self._mineru is None:
            if not settings.rag.mineru_token:
                raise RuntimeError(
                    "MINERU_TOKEN 未配置，无法解析 PDF；请改用 Markdown 文档或补全配置。"
                )
            self._mineru = MinerU(settings.rag.mineru_token)
        return self._mineru

    def _chunk(
        self,
        markdown: str,
        product: Product,
    ) -> tuple[list[ParentChunk], list[Document]]:
        # 1.按照Markdown标题切分父块
        sections = self._markdown_splitter.split_text(markdown)
        parent_chunks: list[ParentChunk] = []
        child_chunks: list[Document] = []

        # 2.遍历父块，继续切分子块
        for section in sections:
            section_path = list(section.metadata.values())
            parent = ParentChunk(
                id=uuid4(),
                product_id=product.id,
                document_name=product.document_name,
                section_path=section_path,
                content=section.page_content,
            )
            parent_chunks.append(parent)

            # 子块通过parent_id关联父块
            section.metadata = {
                "product_id": product.id,
                "parent_id": str(parent.id),
            }
            children = self._child_splitter.split_documents([section])

            # 把章节路径拼接到子块正文中，补充语义上下文
            section_header = "\n".join(section_path) + "\n"
            for child in children:
                child.page_content = section_header + child.page_content
            child_chunks.extend(children)

        return parent_chunks, child_chunks

    def _save_child_chunks(
        self,
        product_id: int,
        child_chunks: list[Document],
    ) -> None:
        # Collection存在时，先删除该产品的旧子块
        if self._vector_store.client.has_collection(
            self._vector_store.collection_name
        ):
            self._vector_store.delete(expr=f"product_id == {product_id}")
        # 再新增子块
        self._vector_store.add_documents(child_chunks)

    async def _save_parent_chunks(
        self,
        product_id: int,
        parent_chunks: list[ParentChunk],
    ) -> None:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                repository = ParentChunkRepository(session)
                # 删除旧父块
                await repository.delete_by_product_id(product_id)
                # 添加新父块
                repository.add_all(parent_chunks)

    def close(self):
        """关闭 MinerU 连接（如果已初始化）。"""

        if self._mineru is not None:
            self._mineru.close()