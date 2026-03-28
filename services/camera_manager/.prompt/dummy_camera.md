# 文件：dummy_camera.py
**职责**：无摄像头环境下的虚拟模拟器。通过读取 `pics` 文件夹下的静态图像作为视频帧输出，便于在缺少硬件的服务器或本地开发环境中测试上层 CV 算法。
**接口**：
- `start()`: 读取 `constants` 指定的图片并缓存到内存中，如图片丢失则生成黑底警告帧。
- `stop()`: 停止模拟器运行状态。
- `get_frame() -> Tuple[bool, Optional[np.ndarray]]`: 根据预设 FPS 模拟延迟，并返回缓存图像的深拷贝副本来模拟连续视频流。
**外部调用示例**：
```python
from services.camera_manager.dummy_camera import DummyCamera
cam = DummyCamera()
cam.start()
success, frame = cam.get_frame() # 获取基于静态图片的虚拟帧
cam.stop()