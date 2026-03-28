import cv2
import threading
from typing import Tuple, Optional
import numpy as np
from .base import BaseCamera
from .constants import DEFAULT_CAMERA_ID, DEFAULT_WIDTH, DEFAULT_HEIGHT

class RealCamera(BaseCamera):
    def __init__(self, camera_id: int = DEFAULT_CAMERA_ID):
        self.camera_id = camera_id
        self.cap = None
        
        # 线程同步相关
        self._frame = None
        self._ret = False
        self._running = False
        self._lock = threading.Lock()
        self._thread = None

    def start(self) -> None:
        if self._running:
            return
            
        self.cap = cv2.VideoCapture(self.camera_id)
        # 尝试设置分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_HEIGHT)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 ID: {self.camera_id}")

        self._running = True
        # 启动守护线程，持续清空 OpenCV 缓冲区并保存最新帧
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _update(self) -> None:
        while self._running:
            ret, frame = self.cap.read()
            with self._lock:
                self._ret = ret
                if ret:
                    self._frame = frame

    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            if self._ret and self._frame is not None:
                # 返回副本，防止多线程下数据被意外修改
                return True, self._frame.copy()
            return False, None

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.cap is not None:
            self.cap.release()