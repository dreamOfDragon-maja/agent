from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.stream import CustomTransformer
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.sse import ServerSentEvent
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exceptions import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository
from app.modules.shopping_plan.schemas import ShoppingAgentContext
from app.agents.schemas import AdditionalInfo
from app.core.logging import get_logger

logger = get_logger(__name__)


def merge_additional_info(target: dict[str, Any], payload: dict[str, Any]) -> None:
    """合并同一轮对话中多个工具产生的卡片数据。

    列表追加、字典合并、其他类型覆盖，避免后一个工具把前一个工具的商品卡/订单卡冲掉。
    """

    for key, value in payload.items():
        current = target.get(key)
        if isinstance(current, list) and isinstance(value, list):
            target[key] = [*current, *value]
        elif isinstance(current, dict) and isinstance(value, dict):
            current.update(value)
        else:
            target[key] = value

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

        # 结束校验事务，避免长时间流式响应占用数据库连接
        await self.repository.session.commit()

        # 2.调用Agent
        # 会话ID
        config = {"configurable": {"thread_id": str(request.thread_id)}}

        # 2.1.如果上一轮还有未确认的 interrupt，用户却发送了普通消息，
        # 直接把消息追加到会话里会让模型拿到“有 tool_calls 却没有 tool 结果”的历史，
        # DeepSeek 会返回 400，且该会话会永久损坏。这里直接拦下并重新下发确认操作。
        if request.decision is None:
            snapshot = await self.agent.aget_state(config)
            if snapshot.interrupts:
                for item in snapshot.interrupts:
                    yield ServerSentEvent(data=item.value, event="interrupt")
                yield ServerSentEvent(
                    data="当前有待确认的操作，请先确认或取消后再继续对话。",
                    event="error",
                )
                return

        # 2.2.消息输入
        if request.decision:
            _input = Command(resume=request.decision)
        else:
            _input = {"messages": [HumanMessage(content=request.message)]}
        # 上下文context
        context = ShoppingAgentContext(user_id=user_id)
        # 2.2.调用
        stream = await (self.agent.astream_events
                        (_input,
                        config,
                        context=context,
                        version="v3",
                        transformers=[CustomTransformer])
                        )

        # 2.2.1.记录AIMessage的ID和引用信息
        final_message_id: str | None = None
        additional_info: AdditionalInfo = {}

        async for event in stream:
            logger.info(event)
            method = event['method']
            # 判断事件类型，可以是messages、interrupts等等
            if method == 'messages':
                data = event['params']['data'][0]
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(data=data.content, event="message")
                elif data.get('delta') and data['delta'].get('text'):
                    yield ServerSentEvent(data=data['delta'].get('text'), event="message")
                elif data.get('event') == 'message-start' and data.get('id'):
                    # 第一个消息片段会传递Message的id
                    final_message_id = data.get('id')

            if method == 'custom':
                data = event["params"]["data"]
                if isinstance(data, dict) and data.get("type") == "additional_info":
                    payload = data.get("data", {})
                    # 同一轮可能先后产生商品、订单、引用等多种卡片，合并后一并持久化
                    if isinstance(payload, dict):
                        merge_additional_info(additional_info, payload)
                    else:
                        additional_info.setdefault("items", []).append(payload)
                    yield ServerSentEvent(data=payload, event="additional_info")

        interrupts = await stream.interrupts()
        for item in interrupts:
            yield ServerSentEvent(data=item.value, event="interrupt")

        if final_message_id and additional_info:
            # 将additional_info更新到state中
            await self.agent.aupdate_state(
                config,
                {"additional_info": {final_message_id: additional_info}}
            )
        # # 2.3.只读取消息中的文本增量
        # async def stream_messages():
        #     async for message in stream.messages:
        #         async for text in message.text:
        #             yield ServerSentEvent(data=text, event="message")
        #
        # # 2.4.判断是否有custom事件
        # async def stream_custom():
        #     async for event in stream.extensions['custom']:
        #         if event.get('type') == 'additional_info':
        #             yield ServerSentEvent(data=event.get('data'), event="additional_info")
        #
        # # 2.5.判断是否有subgraphs事件
        # async def stream_subgraphs():
        #     async for sub_stream in stream.subgraphs:
        #         async for message in sub_stream.messages:
        #             async for text in message.text:
        #                 yield ServerSentEvent(data=text, event="message")
        #
        # # 2.6.合并Message处理和custom事件处理
        # merged = astream.merge(stream_messages(), stream_custom(),stream_subgraphs())
        # async with merged.stream() as streamer:
        #     async for event in streamer:
        #         yield event
        # async for event in stream:
        #     method = event['method']
        #     # 判断事件类型，可以是messages、interrupts等等
        #     if method == 'messages':
        #         data = event['params']['data'][0]
        #         if isinstance(data, AIMessage):
        #             yield ServerSentEvent(data=data.text, event="message")
        #         elif data.get('delta') and data['delta'].get('text'):
        #             yield ServerSentEvent(data=data['delta'].get('text'), event="message")

        # 2.7.更新会话活跃时间，保证会话列表按最近使用排序
        thread.updated_at = datetime.now(timezone.utc)
        await self.repository.session.commit()

        # 2.8.返回结束标识
        yield ServerSentEvent(data="[DONE]", event="done")