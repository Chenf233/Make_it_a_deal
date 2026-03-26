# 模块：Camera Manager
**职责**：封装底层 OpenCV 摄像头操作，对业务层提供统一的视频流获取接口。支持真实摄像头与无摄像头环境的平滑切换。
**对外暴露的核心类/方法**：
- `RealCamera`: 连接物理 USB 摄像头。
- `DummyCamera`: 播放循环视频或生成测试帧。
**外部调用示例**：
```python
from services.camera_manager.real_camera import RealCamera
cam = RealCamera(device_id=0)
success, frame = cam.get_frame()