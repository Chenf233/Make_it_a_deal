from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import cv2
import numpy as np
from typing import Optional

from core.state import app_state
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.schemas import APIResponse, UserOut, ParcelOut, AccessLogOut

router = APIRouter(prefix="/backend", tags=["Backend Management"])

@router.post("/users", response_model=APIResponse)
async def register_user(
    name: str = Form(...),
    phone: str = Form(...),
    file: UploadFile = File(...)
):
    """
    管理员录入新客户，提取人脸特征并热更新至缓存
    """
    # 1. 读取并解码图像
    image_bytes = await file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return APIResponse(code=400, message="图片解码失败，请上传有效图像格式")

    # 2. 提取特征
    embedding = app_state.face_recognizer.extract_feature(frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸或图像质量过低")

    # 3. 存入数据库 (调用 Repository)
    try:
        # 根据您最新的签名：phone: str, username: str, face_feature: np.ndarray
        # 注意：这里直接传 embedding (因为类型是 np.ndarray)，去掉了以前的 .tobytes()
        user_record = UserRepository.add_user(
            phone=phone, 
            username=name, 
            face_feature=embedding, 
            extra_info=None
        )
    except Exception as e:
        return APIResponse(code=500, message=f"数据库写入异常: {str(e)}")

    # 4. 热更新内存特征矩阵
    app_state.add_single_face_to_cache(user_record.id, embedding)

    # 5. 组装标准输出结构
    user_out = UserOut(
        id=user_record.id,
        name=user_record.name,
        phone=user_record.phone,
        is_active=user_record.is_active,
        created_at=user_record.created_at
    )
    
    return APIResponse(message="人员录入成功", data=user_out)

@router.get("/parcels", response_model=APIResponse)
async def get_parcels(status: Optional[int] = None, skip: int = 0, limit: int = 50):
    """
    分页查询包裹列表，支持按状态(1:在库, 2:已取件, 3:异常)过滤
    """
    # 注意参数名变成了 limit 和 offset
    parcels = ParcelRepository.get_all_parcels(limit=limit, offset=skip)
    
    # 序列化 DAO 到 Pydantic Out 模型
    data =[
        ParcelOut(
            id=p.id,
            tracking_no=p.tracking_no,
            company=p.company,
            receiver_name=p.receiver_name,
            receiver_phone=p.receiver_phone,
            status=p.status,
            in_time=p.in_time,
            out_time=p.out_time
        ) for p in parcels
    ]
    return APIResponse(data=data)

@router.get("/logs", response_model=APIResponse)
async def get_access_logs(skip: int = 0, limit: int = 50):
    """
    查询通行与操作日志（包含联表信息）
    """
    # 注意只有 limit 参数
    logs = AccessLogRepository.get_recent_logs(limit=limit)
    
    data =[
        AccessLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=log.user_name,
            user_phone=log.user_phone,
            action_type=log.action_type,
            snapshot_path=log.snapshot_path,
            picked_parcels=log.picked_parcels,
            created_at=log.created_at
        ) for log in logs
    ]
    return APIResponse(data=data)