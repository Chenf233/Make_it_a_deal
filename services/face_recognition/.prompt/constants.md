# 文件：constants.py
**职责**：存储人脸识别模块的算法配置和测试资源路径。
**核心暴露变量**：
- `MODEL_NAME`: 默认使用 `buffalo_l` 以确保高精度。
- `SIMILARITY_THRESHOLD`: 1:1 比对判定为同一人的余弦相似度底线 (默认 0.45)。
- `PROVIDERS`: 优先使用 GPU `CUDAExecutionProvider`，失败则回退 CPU。
- `IMG_FACE_NAN`, `IMG_FACE_1_1`, `IMG_FACE_1_2`, `IMG_FACE_2_1`: 核心测试流程所需的四张真实测试图片绝对路径。
- `DET_SIZE`: 图像检测的默认输入尺寸 (必须是 32 的整数倍)，这里默认是(640，480)。

**外部调用示例**：
```python
from services.face_recognition.constants import SIMILARITY_THRESHOLD
print(f"当前识别阈值为: {SIMILARITY_THRESHOLD}")