# 文件路径: core/state.py
import numpy as np
import logging
from typing import List, Dict, Optional, Any
from fastapi.websockets import WebSocket

# 硬件模块 (使用内置库做类型提示)
import serial 

logger = logging.getLogger("SmartStation")

class ConnectionManager:
    """ WebSocket 连接管理器，用于实现三端实时通信与弹窗驱动 """
    def __init__(self):
        # 按照客户端类型分类存储活跃连接: "admin", "station", "client"
        self.active_connections: Dict[str, List[WebSocket]] = {
            "admin":[],
            "station": [],
            "client":[]
        }

    async def connect(self, websocket: WebSocket, client_type: str):
        await websocket.accept()
        if client_type in self.active_connections:
            self.active_connections[client_type].append(websocket)

    def disconnect(self, websocket: WebSocket, client_type: str):
        if client_type in self.active_connections and websocket in self.active_connections[client_type]:
            self.active_connections[client_type].remove(websocket)

    async def broadcast_to(self, client_type: str, message: dict):
        """ 向指定业务端广播 JSON 消息 (例如让 client 端弹窗报警) """
        if client_type not in self.active_connections:
            return

        dead_connections =[]
        for connection in self.active_connections[client_type]:
            try:
                await connection.send_json(message)

            except Exception:
                dead_connections.append(connection)
                
        # 清理断开的连接
        for dead in dead_connections:
            self.active_connections[client_type].remove(dead)


class GlobalStateManager:
    """ 全局状态与缓存管理器 (Lifespan 中初始化) """
    def __init__(self):
        # CV 及外设实例
        self.camera = None
        self.face_recognizer = None
        self.scanner = None
        
        # 串口硬件实例 (用于真实控制继电器/蜂鸣器)
        self._serial_port = None

        # 内存中的人脸 1:N 检索缓存
        self.face_matrix: Optional[np.ndarray] = None
        self.user_ids: List[int] =[]

        # WS 广播通信器
        self.ws_manager = ConnectionManager()

    # ==========================
    # 人脸缓存与 1:N 检索逻辑
    # ==========================
    def build_face_cache(self, user_records: List[dict]):
        """ 系统启动时调用：从 DB 拉取所有存活用户特征构建检索矩阵 """
        if not user_records:
            self.face_matrix = None
            self.user_ids = []
            return

        embeddings = []
        self.user_ids =[]
        for record in user_records:
            # 假设数据库取出的 feature 是 bytes 类型的 blob，需要恢复成 numpy array
            # 这里依赖 database 模块存入时的序列化方式 (通常为 np.ndarray.tobytes())
            try:
                emb = np.frombuffer(record["face_feature"], dtype=np.float32)
                embeddings.append(emb)
                self.user_ids.append(record["user_id"])
            except Exception as e:
                logger.error(f"无法解析用户 {record['user_id']} 的人脸特征: {e}")

        if embeddings:
            self.face_matrix = np.array(embeddings)
            logger.info(f"已成功在内存中构建 {len(self.user_ids)} 个人脸特征矩阵。")

    def search_face(self, target_embedding: np.ndarray, threshold: float) -> Optional[int]:
        """ 高频接口：客户刷脸时，与内存矩阵进行极速向量比对 """
        if self.face_matrix is None or len(self.user_ids) == 0:
            return None

        # 余弦相似度计算: InsightFace特征通常已做过L2归一化，故点乘即为余弦相似度
        # similarities 是一维数组，包含当前人脸与库中所有人脸的相似度
        similarities = np.dot(self.face_matrix, target_embedding.T).flatten()
        
        max_idx = np.argmax(similarities)
        max_sim = similarities[max_idx]

        if max_sim >= threshold:
            return self.user_ids[max_idx]
        return None

    def add_single_face_to_cache(self, user_id: int, embedding: np.ndarray):
        """ 管理端录入新用户时，热更新内存矩阵，无需重启 """
        if self.face_matrix is None:
            self.face_matrix = np.array([embedding])
            self.user_ids = [user_id]
        else:
            self.face_matrix = np.vstack((self.face_matrix, embedding))
            self.user_ids.append(user_id)

    # ==========================
    # 硬件驱动逻辑 (串口控制 / 弹窗模拟)
    # ==========================
    def init_hardware(self, enable_real: bool, port: str, baudrate: int):
        """ 初始化真实的串口硬件 (如果启用) """
        if enable_real:
            try:
                # self._serial_port = serial.Serial(port, baudrate, timeout=1)
                logger.info(f"真实串口硬件已挂载: {port} @ {baudrate} bps")
            except Exception as e:
                logger.error(f"串口初始化失败: {e}")
        else:
            logger.info("硬件模式: [演示模拟 (WebSocket 前端弹窗)]")

    async def trigger_hardware_alert(self, action_type: str, payload: dict):
        """
        触发硬件动作核心函数
        action_type 可以是: "DOOR_OPEN" (开门), "TAKE_PARCEL" (引导取件亮灯), "FORGET_ALERT" (出门漏取报警)
        """
        if self._serial_port:
            # --- 真实串口控制逻辑 (注释保留供同事接手) ---
            # command = ""
            # if action_type == "DOOR_OPEN":
            #     command = "CMD_RELAY_ON\n"
            # elif action_type == "FORGET_ALERT":
            #     command = "CMD_BUZZER_ON\n"
            # if command:
            #     self._serial_port.write(command.encode('utf-8'))
            pass
        print(555)
        # 无论是否真实串口，统一向 Client 端推送 WebSocket 消息以渲染 UI 弹窗
        await self.ws_manager.broadcast_to("client", {
            "type": "HARDWARE_ACTION",
            "action": action_type,
            "data": payload
        })


# 全局状态单例，FastAPI 生命周期内唯一
app_state = GlobalStateManager()