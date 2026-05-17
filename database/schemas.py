from pydantic import BaseModel, Field
from typing import Optional, List, Any

# ==========================
# 1. 通用响应封装
# ==========================
class APIResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None

# ==========================
# 2. 核心业务实体输出模型 (Out)
# ==========================
class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    is_active: int
    created_at: str

class ParcelOut(BaseModel):
    id: int
    tracking_no: str
    company: str
    receiver_name: str
    receiver_phone: str
    cabinet_number: str = Field(..., description="货柜号，同时作为取件码展示")
    status: int = Field(..., description="1: 在库, 2: 已取件, 3: 异常")
    in_time: str
    out_time: Optional[str] = None

class AccessLogOut(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    action_type: str = Field(..., description="IN(进门) 或 OUT(出门)")
    snapshot_path: str
    picked_parcels: Optional[str] = None
    created_at: str

# ==========================
# 3. 后台管理端交互模型 (Backend)
# ==========================
class ParcelStatusUpdate(BaseModel):
    status: int = Field(..., ge=1, le=3)

# ==========================
# 4. 驿站工作端交互模型 (Station)
# ==========================
class ScanResultData(BaseModel):
    tracking_no: str
    company: str
    receiver_name: str
    receiver_phone: str
    cabinet_number: str  # 入库后分配的货柜号
    is_new_user: bool = Field(False)

# ==========================
# 5. 客户体验端交互模型 (Client)
# ==========================
class FaceAuthResult(BaseModel):
    user: UserOut
    active_parcels: List[ParcelOut] = Field(default_factory=list)
    action: str = Field(..., description="IN(进门) 或 OUT(出门)")
    has_forgotten_parcels: bool = Field(False, description="出门时判定是否有漏拿的在库包裹")