from app.core.exceptions import ApplicationError


class AfterSalesOrderNotFoundError(ApplicationError):
    """订单不存在或不属于当前用户，不能发起售后"""

    status_code = 404
    code = "AFTER_SALES_ORDER_NOT_FOUND"
    message = "订单不存在或不属于当前用户，无法发起售后"


class AfterSalesOrderStateError(ApplicationError):
    """订单状态不支持发起售后"""

    status_code = 400
    code = "AFTER_SALES_ORDER_STATE_INVALID"
    message = "当前订单状态不支持发起售后，请确认订单已支付或已完成"
