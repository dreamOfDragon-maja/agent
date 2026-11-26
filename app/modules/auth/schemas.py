from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    """登录用户信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    """登录成功后的令牌与用户信息"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
