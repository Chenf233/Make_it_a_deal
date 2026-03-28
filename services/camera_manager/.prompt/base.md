# 文件：base.py
**职责**：定义摄像头的抽象基类 `BaseCamera`，规范所有摄像头实现类的标准接口，遵循依赖倒置原则。确保上层业务逻辑调用摄像头时，无需关注底层硬件细节。
**接口**：
- `start()`: 初始化并启动视频流获取。
- `stop()`: 停止视频流并释放硬件或内存资源。
- `get_frame() -> Tuple[bool, Optional[np.ndarray]]`: 获取最新的一帧图像，返回成功标志及 BGR 格式的 numpy 数组。
**外部调用示例**：
```python
# 该文件仅作继承使用，不直接实例化
from .base import BaseCamera

class MyCamera(BaseCamera):
    def start(self): pass
    def stop(self): pass
    def get_frame(self): return True, frame