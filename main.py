# 文件：main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# 导入内部模块
from core.config import settings
from core.state import app_state
from database.db_manager import DatabaseManager
from database.models import UserRepository

# 导入独立 CV/硬件 服务
from services.camera_manager import get_camera
from services.face_recognition import FaceRecognizer
from services.scanner import QRScanner

# 导入路由 (稍后我们将实现这些文件)
from routers import backend_api, station_api, client_api

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SmartStation")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理器：控制启动与关闭逻辑
    """
    logger.info("=== 系统正在启动 ===")
    
    # 1. 初始化数据库表结构 (幂等操作)
    DatabaseManager.init_db()
    logger.info("数据库初始化完成。")

    # 2. 实例化并挂载 CV 与底层服务到全局状态 (State)
    app_state.camera = get_camera()
    app_state.camera.start()
    logger.info("摄像头线程已启动。")

    app_state.face_recognizer = FaceRecognizer()
    logger.info("InsightFace 人脸识别引擎加载完毕。")

    app_state.scanner = QRScanner()
    logger.info("条码/二维码解析引擎加载完毕。")

    # 3. 预热内存人脸 1:N 检索矩阵
    # 启动时进行一次全量同步读取是安全的，它准备好了再对外提供服务
    active_users = UserRepository.get_all_active_faces()
    app_state.build_face_cache(active_users)
    logger.info("=== 系统启动完毕，准备接收请求 ===")

    yield  # ---------------- 分界线：系统运行中 ----------------

    logger.info("=== 系统正在关闭 ===")
    # 4. 安全回收硬件资源
    if app_state.camera:
        app_state.camera.stop()
        logger.info("摄像头线程已安全释放。")
    logger.info("=== 系统已安全退出 ===")


# 实例化 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# 配置跨域请求 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载模板引擎
templates = Jinja2Templates(directory="templates")


# ==========================
# 页面路由 (渲染纯 HTML)
# ==========================
@app.get("/backend", response_class=HTMLResponse, summary="后台管理端页面")
async def backend_page(request: Request):
    # 修改这里：使用显式的关键字参数 request= 和 name=
    return templates.TemplateResponse(request=request, name="backend.html")

@app.get("/station", response_class=HTMLResponse, summary="驿站工作端页面")
async def station_page(request: Request):
    # 修改这里
    return templates.TemplateResponse(request=request, name="station.html")

@app.get("/client", response_class=HTMLResponse, summary="客户体验端页面")
async def client_page(request: Request):
    # 修改这里
    return templates.TemplateResponse(request=request, name="client.html")


# ==========================
# 全局 WebSocket 通信枢纽
# ==========================
@app.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str):
    """
    处理三端 WebSocket 长连接
    client_type 取值: "admin", "station", "client"
    """
    await app_state.ws_manager.connect(websocket, client_type)
    try:
        while True:
            # 保持连接活跃，并可接收前端的心跳或指令
            data = await websocket.receive_text()
            # 可以在这里处理前端主动发起的特殊 WS 消息
    except WebSocketDisconnect:
        app_state.ws_manager.disconnect(websocket, client_type)


# ==========================
# 挂载业务路由 (暂注释，待编写)
# ==========================
app.include_router(backend_api.router, prefix="/api")
app.include_router(station_api.router, prefix="/api")
app.include_router(client_api.router, prefix="/api")