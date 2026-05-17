# 文件：schemas.py

**职责**：定义全系统 API 的数据模型，用于 FastAPI 自动校验与序列化。更新后已包含货柜号字段。

**核心模型**：
- `APIResponse`：统一返回 `{code, message, data}`。
- `UserOut`：用户输出（不含 BLOB）。
- `ParcelOut`：包裹输出，**已添加 `cabinet_number` 字段**，前端直接渲染为取件码。
- `AccessLogOut`：进出日志输出。
- `ParcelStatusUpdate`：后台修改包裹状态的请求体。
- `ScanResultData`：入库成功返回给前端展示的数据，**含 `cabinet_number`**。
- `FaceAuthResult`：刷脸认证后综合返回（用户信息 + 在库包裹列表 + 是否漏拿标志）。

**外部调用示例**：
```python
from database.schemas import ParcelOut
# 在路由中返回 ParcelOut 实例，Pydantic 自动校验
```