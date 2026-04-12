# 文件：config.py
**职责**：提供纯粹的 FastAPI 框架级别运行配置（主机、端口、CORS、应用元数据），支持从 `.env` 读取。
**接口**：
- `settings`: `Settings` 类的全局实例化对象。
**外部调用示例**：
```python
from core.config import settings
app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)