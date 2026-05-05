# 模块：routers
**职责**：FastAPI 的路由控制层。严格划分为管理端、驿站端、客户端三大独立接口体系。严禁包含 CV 计算或复杂业务算法，仅负责接收网络请求，调度 `core.state` 和 `database`，并始终返回 `database.schemas` 定义的统一结构体（如 `APIResponse`）。