# 文件：database/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Any

# ==========================
# 1. 通用响应封装
# ==========================
class APIResponse(BaseModel):
    """统一的 API JSON 返回格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


# ==========================
# 2. 核心业务实体输出模型 (Out)
# ==========================
class UserOut(BaseModel):
    """用户数据输出 (已剔除 BLOB 人脸特征，用于后台列表展示)"""
    id: int
    name: str
    phone: str
    is_active: int
    created_at: str

class ParcelOut(BaseModel):
    """包裹数据输出"""
    id: int
    tracking_no: str
    company: str
    receiver_name: str
    receiver_phone: str
    status: int = Field(..., description="1: 在库, 2: 已取件, 3: 异常")
    in_time: str
    out_time: Optional[str] = None

class AccessLogOut(BaseModel):
    """进出门日志输出 (后台看板使用，包含联表查出的用户信息)"""
    id: int
    user_id: int
    user_name: Optional[str] = None   # 联表补齐
    user_phone: Optional[str] = None  # 联表补齐
    action_type: str = Field(..., description="IN(进门) 或 OUT(出门)")
    snapshot_path: str
    picked_parcels: Optional[str] = None 
    created_at: str


# ==========================
# 3. 后台管理端交互模型 (Backend)
# ==========================
# 录入用户的请求不在这里定义 Pydantic，因为包含图片文件上传，FastAPI 会直接使用 Form 和 UploadFile

class ParcelStatusUpdate(BaseModel):
    """管理员手动更新包裹状态的请求体"""
    status: int = Field(..., ge=1, le=3)


# ==========================
# 4. 驿站工作端交互模型 (Station)
# ==========================
class ScanResultData(BaseModel):
    """单次扫码入库成功后返回给前端展示的数据"""
    tracking_no: str
    company: str
    receiver_name: str
    receiver_phone: str
    is_new_user: bool = Field(False, description="是否是未录入系统的新客户(触发异常)")


# ==========================
# 5. 客户体验端交互模型 (Client)
# ==========================
class FaceAuthResult(BaseModel):
    """刷脸成功后的综合返回数据"""
    user: UserOut
    active_parcels: List[ParcelOut] = Field(default_factory=list, description="该用户当前在库的所有包裹")
    action: str = Field(..., description="IN(进门) 或 OUT(出门)")
    has_forgotten_parcels: bool = Field(False, description="出门时判定是否有漏拿的在库包裹")