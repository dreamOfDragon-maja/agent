from uuid import UUID

from app.core.security import CurrentUser
from app.modules.chat_thread.schemas import ChatHistoryResponse
from fastapi import APIRouter, Depends, Response, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from .schemas import *
from .service import ChatThreadService

router = APIRouter(prefix="/api/v1/chat-threads", tags=["会话管理的接口"])

async def get_service(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ChatThreadService:
    return ChatThreadService(
        session=session,
        agent=request.app.state.agent,
    )


@router.post("", response_model=ChatThreadResponse)
async def create_chat_thread(
        request: ChatThreadCreate,
        user: CurrentUser,
        service: ChatThreadService = Depends(get_service),
):
    """创建会话"""

    return await service.add(user.id, request.title)

@router.get("", response_model=list[ChatThreadResponse])
async def list_chat_threads(
    user: CurrentUser,
    service: ChatThreadService = Depends(get_service),
):
    """查询当前用户的会话列表"""

    return await service.list_by_user(user.id)

@router.patch("/{thread_id}", response_model=ChatThreadResponse)
async def rename(
    thread_id: UUID,
    request: ChatThreadCreate,
    user: CurrentUser,
    service: ChatThreadService = Depends(get_service),
):
    """重命名会话"""

    return await service.rename(thread_id, user.id, request.title)

@router.delete(
    "/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat_thread(
    thread_id: UUID,
    user: CurrentUser,
    service: ChatThreadService = Depends(get_service),
) -> Response:
    """删除指定会话"""

    await service.delete(thread_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{thread_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    thread_id: UUID,
    user: CurrentUser,
    service: ChatThreadService = Depends(get_service),
):
    """查询指定会话的历史消息"""

    return await service.get_history(thread_id, user.id)
