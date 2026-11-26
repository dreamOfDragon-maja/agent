from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infra.database import get_session
from app.modules.user.models import User

# 使用 argon2 进行密码哈希；pwdlib 会自动选择当前推荐参数
password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """把明文密码转换为可持久化的哈希值。"""

    return password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与数据库中的哈希是否匹配。"""

    try:
        return password_hasher.verify(plain_password, password_hash)
    except Exception:
        return False


def create_access_token(user_id: int) -> tuple[str, int]:
    """生成 JWT，返回令牌和有效期秒数。"""

    expires_in = settings.auth.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
    )
    return token, expires_in


def decode_access_token(token: str) -> int:
    """解析 JWT 并返回用户 ID；无效令牌统一抛出 401。"""

    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret,
            algorithms=[settings.auth.jwt_algorithm],
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return user_id


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """FastAPI 依赖：从 Authorization 头解析当前登录用户。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
