# 模块：pickup (`__init__.py`)
**职责**：向客户体验端路由提供包裹确取能力。封装扫码验证与状态更新流程，完全无状态，每次调用独立。  
**接口**：  
- 暴露 `PickupHandler` 核心类，供路由层依赖注入或直接实例化使用。  
**外部调用示例**：
```python
from services.pickup import PickupHandler
handler = PickupHandler()
success, message, info = await handler.handle_pickup(user_id)
```