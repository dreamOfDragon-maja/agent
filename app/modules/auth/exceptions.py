from app.core.exceptions import ApplicationError


class InvalidCredentialsError(ApplicationError):
    """用户名或密码错误"""

    status_code = 401
    code = "INVALID_CREDENTIALS"
    message = "用户名或密码错误"


class AccountDisabledError(ApplicationError):
    """账号已禁用"""

    status_code = 403
    code = "ACCOUNT_DISABLED"
    message = "账号已被禁用，请联系管理员"
