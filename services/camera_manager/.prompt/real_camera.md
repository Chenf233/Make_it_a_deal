# 文件：real_camera.py
**职责**：封装 `cv2.VideoCapture`，内部维护一个后台线程不断读取最新帧，避免缓冲区堆积导致画面延迟。
**接口**：
- `start()`: 开启后台读帧线程
- `stop()`: 释放摄像头并回收线程
- `get_frame() -> Tuple[bool, np.ndarray]`: 非阻塞获取最新的一帧
**外部调用示例**：
```python
cam = RealCamera(camera_id=0)
cam.start()
success, frame = cam.get_frame()
cam.stop()