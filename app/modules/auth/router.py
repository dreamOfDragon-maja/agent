from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.infra.database import get_session
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["登录与账号接口"])


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


@router.post("/login", response_model=TokenResponse, summary="账号密码登录")
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user, token, expires_in = await service.authenticate(
        request.username,
        request.password,
    )
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, summary="获取当前登录用户")
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
