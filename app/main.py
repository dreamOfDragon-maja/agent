from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import ApplicationError
from app.core.config import settings
from app.core.logging import configure_logging,get_logger

#日志配置
configure_logging(settings.logging.level)
#获取日志的记录器
logger = get_logger(__name__)

#初始化生命周期钩子函数
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("项目启动中，正在初始化...")
    from app.infra.database import check_database,close_database
    from app.infra.checkpointer import init_checkpointer,close_checkpointer
    from app.agents.orchestrator import init_insurance_orchestrator
    from app.rag import close_rag  # 导入模块就会初始化
    try:
        #初始化数据库连接池
        await check_database()
        #初始化checkpointer
        checkpointer = await init_checkpointer()
        #初始化agent,保存在FastAPI的全局state中
        app.state.agent = await init_insurance_orchestrator(checkpointer)
        yield
    finally:
        close_rag()
        await close_database()
        await close_checkpointer()

#初始化FastAPI
app = FastAPI(
    title=settings.app.name,
    debug=settings.app.debug,
    lifespan = lifespan
)

#商品
from app.modules.product.router import router as product_router
# 创建 app 后注册路由
app.include_router(product_router)

#会话管理
from app.modules.chat_thread.router import router as chat_thread_router
app.include_router(chat_thread_router)

#聊天
from app.modules.chat.router import router as chat_router
app.include_router(chat_router)

@app.exception_handler(ApplicationError)
async def handle_application_error(
    request: Request,
    exc: ApplicationError, # 捕获到的异常（这里用自定义异常基类捕获，所有业务异常都会匹配到）
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, # 异常中自带status
        content={
            "code": exc.code,        # 异常中自带code
            "message": exc.message,  # 异常中自带message
        },
    )

#healthy接口
@app.get("/healthy",summary="健康检测的接口")
async def healthy()->dict[str, str]:
    logger.info("健康检测接口正常调用")
    return {"status": "ok"}

if __name__ == "__main__":
    import sys
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        loop= "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
    )