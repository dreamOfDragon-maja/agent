from app.core.exceptions import ApplicationError


class ShoppingPlanNotFoundError(ApplicationError):
    """购物方案不存在或不属于当前用户"""

    status_code = 404
    code = "SHOPPING_PLAN_NOT_FOUND"
    message = "购物方案不存在或不属于当前用户"


class ShoppingPlanItemNotFoundError(ApplicationError):
    """购物方案项不存在"""

    status_code = 404
    code = "SHOPPING_PLAN_ITEM_NOT_FOUND"
    message = "购物方案项不存在"
