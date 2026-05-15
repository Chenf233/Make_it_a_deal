from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import cv2
import numpy as np
import json
from datetime import datetime
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
    image_bytes = await file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return APIResponse(code=400, message="图片解码失败")

    embedding = app_state.face_recognizer.extract_feature(frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸")

    try:
        # 1. 修复：获取返回的 int 类型 user_id
        user_id = UserRepository.add_user(
            phone=phone, 
            username=name, 
            face_feature=embedding, 
            extra_info=None
        )
    except Exception as e:
        return APIResponse(code=500, message=f"数据库写入异常: {str(e)}")

    # 2. 热更新内存矩阵
    app_state.add_single_face_to_cache(user_id, embedding)

    # 3. 修复：因为不需要再去查一次数据库，直接用刚才的数据组装 UserOut
    user_out = UserOut(
        id=user_id,
        name=name,
        phone=phone,
        is_active=1,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    return APIResponse(message="人员录入成功", data=user_out)

@router.get("/parcels", response_model=APIResponse)
async def get_parcels(status: Optional[int] = None, skip: int = 0, limit: int = 50):
    parcels = ParcelRepository.get_all_parcels(limit=limit, offset=skip)
    data =[]
    for p in parcels:
        # 修复：安全解析 extra_info JSON 字符串，并通过字典键访问
        extra = json.loads(p.get("extra_info") or "{}") if isinstance(p, dict) else json.loads(p["extra_info"] or "{}")
        data.append(ParcelOut(
            id=p["parcel_id"],             # 映射 parcel_id -> id
            tracking_no=p["tracking_no"],
            company=extra.get("company", "未知"), 
            receiver_name=extra.get("receiver_name", "未知"),
            receiver_phone=p["receiver_phone"],
            status=p["status"],
            in_time=p["in_time"],
            out_time=p["out_time"]
        ))
    return APIResponse(data=data)

@router.get("/logs", response_model=APIResponse)
async def get_access_logs(skip: int = 0, limit: int = 50):
    logs = AccessLogRepository.get_recent_logs(limit=limit)
    data =[]
    for log in logs:
        data.append(AccessLogOut(
            id=log["log_id"],               # 映射 log_id -> id
            user_id=log["user_id"],
            user_name=log.get("username"), # 联表查询可能没有
            user_phone=log.get("phone"),
            action_type=log["action_type"],
            snapshot_path=log["snapshot_path"] or "",
            picked_parcels=log["picked_parcels"],
            created_at=log["timestamp"]     # 映射 timestamp -> created_at
        ))
    return APIResponse(data=data)