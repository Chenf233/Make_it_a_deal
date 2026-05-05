# 文件：schemas.py
**职责**：通过 Pydantic 定义全系统的 HTTP API 请求体验证规则与标准响应序列化结构，确保端到端交互数据的类型安全。
**接口**：
- `APIResponse`: 全局统一的 JSON 返回信封（code, message, data）。
- `UserOut`, `ParcelOut`, `AccessLogOut`: 核心业务实体的标准输出模型。
- `ScanResultData`, `FaceAuthResult`: 针对不同终端业务场景的复合聚合输出模型。
**外部调用示例**：
```python
from database.schemas import APIResponse, ParcelOut

@router.get("/parcels", response_model=APIResponse)
async def get_parcels():
    parcels = ParcelRepository.get_all()
    # Pydantic 会自动将 DAO 对象转化为 ParcelOut 字典
    return APIResponse(data=[ParcelOut(**p.__dict__) for p in parcels])