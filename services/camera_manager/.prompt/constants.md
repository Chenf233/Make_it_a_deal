# 文件：constants.py
**职责**：集中管理摄像头模块的底层魔术数字、默认配置和资源路径，确保修改配置时仅需触碰此文件。
**核心暴露变量**：
- `CAMERA_TYPE`: 决定系统使用真实摄像头还是虚拟摄像头 (`"real"` 或 `"dummy"`)
- `DEFAULT_CAMERA_ID`, `DEFAULT_WIDTH`, `DEFAULT_HEIGHT`: 物理摄像头配置
- `DEFAULT_FPS`: 模拟摄像头延迟控制
- `DUMMY_IMAGE_PATH`: 虚拟摄像头加载的测试图片绝对路径
**外部调用示例**：
```python
from services.camera_manager.constants import CAMERA_TYPE
if CAMERA_TYPE == "dummy":
    print("当前为无硬件模拟模式")