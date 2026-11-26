from app.core.exceptions import ApplicationError


class OrderNotFoundError(ApplicationError):
    """订单不存在或不属于当前用户"""

    status_code = 404
    code = "ORDER_NOT_FOUND"
    message = "订单不存在或不属于当前用户"


class OrderStateError(ApplicationError):
    """订单状态不允许当前操作"""

    status_code = 400
    code = "ORDER_STATE_INVALID"
    message = "当前订单状态不允许该操作"


class OrderItemNotAvailableError(ApplicationError):
    """方案项已被下单或不可用"""

    status_code = 400
    code = "ORDER_ITEM_NOT_AVAILABLE"
    message = "该方案项已下单或不可用，请刷新后重试"
