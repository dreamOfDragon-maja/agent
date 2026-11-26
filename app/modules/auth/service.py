from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.modules.auth.exceptions import AccountDisabledError, InvalidCredentialsError
from app.modules.user.models import User


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> tuple[User, str, int]:
        """校验账号密码，返回用户、JWT 和有效期秒数。"""

        user = await self.session.scalar(
            select(User).where(User.username == username.strip())
        )
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        if user.status != "active":
            raise AccountDisabledError

        token, expires_in = create_access_token(user.id)
        return user, token, expires_in

    async def get_user(self, user_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id))
