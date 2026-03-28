# 文件：core.py
**职责**：封装 InsightFace 分析引擎，处理人脸检测、特征提取（Embedding）和相似度计算。支持依赖注入以动态切换计算提供者（CPU/GPU）。
**接口**：
- `__init__(providers: Optional[List[str]] = None)`: 允许传入特定的执行提供者列表，为空则使用 `constants` 默认配置。
- `extract_feature(frame: np.ndarray) -> Optional[np.ndarray]`: 输入 BGR 图像，返回 512 维特征向量或 None。
- `compute_similarity(emb1, emb2) -> float`: 计算余弦相似度。
- `is_match(emb1, emb2, threshold) -> bool`: 判断是否为同一人。
**外部调用示例**：
```python
from services.face_recognition.core import FaceRecognizer
# 强制使用 CPU 进行实例化测试
recognizer = FaceRecognizer(providers=['CPUExecutionProvider'])
emb = recognizer.extract_feature(frame)