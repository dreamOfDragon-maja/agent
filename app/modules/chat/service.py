from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.stream import CustomTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.sse import ServerSentEvent
from aiostream import stream as astream
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository
from app.modules.insurance_plan.schemas import InsuranceAgentContext

class ChatService:
    def __init__(self, session: AsyncSession, agent: CompiledStateGraph):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def chat_stream(
        self,
        user_id: int,
        request: ChatRequest,
    ) -> str:
        # 1.校验会话是否属于当前用户
        thread = await self.repository.find_owned(
            request.thread_id,
            user_id,
        )
        if thread is None:
            raise ChatThreadNotFoundError

        # 2.调用Agent
        # 2.1.消息输入
        _input = {"messages": [HumanMessage(content=request.message)]}
        # 会话ID
        config = {"configurable": {"thread_id": str(request.thread_id)}}
        # 上下文context
        context = InsuranceAgentContext(user_id=user_id)
        # 2.2.调用
        stream = await self.agent.astream_events(_input, config,context=context,version="v3",transformers=[CustomTransformer])

        # 2.3.只读取消息中的文本增量
        async def stream_messages():
            async for message in stream.messages:
                async for text in message.text:
                    yield ServerSentEvent(data=text, event="message")

        # 2.4.判断是否有custom事件
        async def stream_custom():
            async for event in stream.extensions['custom']:
                if event.get('type') == 'additional_info':
                    yield ServerSentEvent(data=event.get('data'), event="additional_info")

        # 2.5.合并Message处理和custom事件处理
        merged = astream.merge(stream_messages(), stream_custom())
        async with merged.stream() as streamer:
            async for event in streamer:
                yield event
        # 2.6.返回结束标识
        yield ServerSentEvent(data="[DONE]", event="done")