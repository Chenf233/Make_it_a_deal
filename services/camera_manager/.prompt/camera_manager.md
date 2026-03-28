# 模块：camera_manager (`__init__.py`)
**职责**：封装底层 OpenCV 摄像头操作，解决阻塞主线程以及多端同时拉流时的帧同步问题。通过工厂函数提供开箱即用的摄像头实例。
**接口**：
- `get_camera() -> BaseCamera`: 工厂方法，读取 `constants.CAMERA_TYPE` 自动返回 `RealCamera` 或 `DummyCamera` 实例。
- `BaseCamera`, `RealCamera`, `DummyCamera`: 提供核心类供外部做类型提示或特殊需求时显式调用。
**外部调用示例**：
```python
from services.camera_manager import get_camera
cam = get_camera() # 业务层无需知道底层是真实的还是虚拟的
cam.start()
success, frame = cam.get_frame()