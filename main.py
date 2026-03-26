from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: 系统启动时执行：初始化数据库连接池、预加载 InsightFace 模型
    print("🚀 SmartStation 系统启动，正在加载 AI 模型和数据库...")
    yield
    # TODO: 系统关闭时执行：释放 GPU 显存、关闭摄像头、断开数据库
    print("💤 SmartStation 系统关闭，释放资源。")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "SmartStation Backend is running!"}

# TODO: 后续在这里 include_router 引入各端 API