# 模块：face_recognition (`__init__.py`)
**职责**：向外部业务路由提供统一的高精度人脸识别能力。
**接口**：
暴露 `FaceRecognizer` 核心类与 `SIMILARITY_THRESHOLD` 默认阈值，供依赖注入（DI）或全局单例化使用。
**外部调用示例**：
```python
from services.face_recognition import FaceRecognizer
recognizer = FaceRecognizer()