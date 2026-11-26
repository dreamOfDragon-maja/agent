from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from .repository import ChatThreadRepository
from .models import ChatThread
from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import AIMessage, HumanMessage

from app.modules.chat_thread.schemas import (
    ChatHistoryResponse,
    ChatMessageResponse,
)

class ChatThreadService:

    def __init__(self, session: AsyncSession,agent:CompiledStateGraph):
        self.session = session
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def add(self, user_id: int , title: str):
        # 鉴权依赖可能已经在同一个 Session 上开启了事务，
        # 这里不能再次 session.begin()，直接 commit/rollback 共享事务。
        try:
            chat_thread = ChatThread(user_id=user_id, title=title)
            await self.repository.add(chat_thread)
            await self.session.commit()
            await self.session.refresh(chat_thread)
            return chat_thread
        except Exception:
            await self.session.rollback()
            raise

    async def list_by_user(self, user_id: int) -> list[ChatThread]:
        return await self.repository.list_by_user(user_id)

    async def rename(
            self,
            thread_id: UUID,
            user_id: int,
            title: str
    ) -> ChatThread:
        thread = await self.repository.find_owned(thread_id, user_id)
        if thread is None:
            raise ChatThreadNotFoundError

        try:
            thread.title = title
            await self.session.commit()
            await self.session.refresh(thread)
            return thread
        except Exception:
            await self.session.rollback()
            raise

    async def delete(
            self,
            thread_id: UUID,
            user_id: int,
    ) -> None:
        thread = await self.repository.find_owned(thread_id, user_id)
        if thread is None:
            raise ChatThreadNotFoundError

        try:
            # 删除checkpointer中的会话状态
            await self.agent.checkpointer.adelete_thread(str(thread_id))
            # 删除会话元数据
            await self.repository.delete(thread)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def get_history(
            self,
            thread_id: UUID,
            user_id: int,
    ) -> ChatHistoryResponse:
        # 1.校验会话归属
        thread = await self.repository.find_owned(thread_id, user_id)
        if thread is None:
            raise ChatThreadNotFoundError

        # 2.读取Agent最新状态
        config = {"configurable": {"thread_id": str(thread_id)}}
        snapshot = await self.agent.aget_state(config)
        additional_infos = snapshot.values.get("additional_info") or {}

        # 3.只保留用户消息和AI消息
        messages = []
        for message in snapshot.values.get("messages", []):
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue

            if message.text:
                messages.append(
                    ChatMessageResponse(
                        role=role,
                        content=message.text,
                        additional_info=additional_infos.get(message.id),
                    )
                )
        # 处理interrupt：刷新页面后仍能恢复待确认的操作
        interrupt = snapshot.interrupts[0].value if snapshot.interrupts else None

        return ChatHistoryResponse(
            thread_id=thread_id,
            messages=messages,
            interrupt=interrupt,
        )
