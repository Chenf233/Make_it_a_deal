"""
backend_api.py - 后台管理端 API 路由
====================
负责人员录入、包裹管理看板、进出日志查询。
所有接口均返回统一的 APIResponse 结构，数据模型严格遵循 database/schemas.py。
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Literal, Optional, List

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from fastapi import Body
from pydantic import BaseModel, Field
from typing import Optional

from core.state import app_state
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.schemas import (
    APIResponse,
    UserOut,
    ParcelOut,
    AccessLogOut,
)

class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    extra_info: Optional[dict] = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backend", tags=["Backend Management"])


# ========================
# 辅助函数
# ========================
def _build_user_phone_name_map() -> dict:
    """构建手机号 -> 用户姓名的映射，用于包裹列表展示收件人真实姓名。"""
    users = UserRepository.get_all_users(limit=1000, offset=0)  # 假设管理端用户总数有限
    return {u["phone"]: u["username"] for u in users if u.get("phone")}


# ========================
# 人员管理
# ========================
@router.post("/users", response_model=APIResponse)
async def register_user(
    name: str = Form(..., min_length=1, max_length=50),
    phone: str = Form(..., pattern=r"^1[3-9]\d{9}$"),
    file: UploadFile = File(...)
):
    """
    注册新用户，上传照片提取人脸特征并存储。
    """
    # 1. 图片解码
    image_bytes = await file.read()
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return APIResponse(code=400, message="图片解码失败，请上传有效的图片文件")

    # 2. 提取人脸特征
    embedding = await asyncio.get_event_loop().run_in_executor(
        None, app_state.face_recognizer.extract_feature, frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸，请上传包含清晰正面照的图片")

    # 3. 写入数据库（捕获特定异常）
    try:
        user_id = UserRepository.add_user(
            phone=phone,
            username=name,
            face_feature=embedding,
            extra_info=None
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "unique" in error_msg or "constraint" in error_msg:
            return APIResponse(code=409, message="该手机号已被注册")
        logger.exception("数据库写入异常")
        return APIResponse(code=500, message="服务器内部错误，人员录入失败")

    # 4. 热更新内存特征缓存（失败仅记录日志，不影响主流程）
    try:
        app_state.add_single_face_to_cache(user_id, embedding)
    except Exception:
        logger.exception("人脸特征缓存更新失败，重启服务后将自动重建")

    # 5. 构造响应（时间格式统一）
    user_out = UserOut(
        id=user_id,
        name=name,
        phone=phone,
        is_active=1,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    return APIResponse(message="人员录入成功", data=user_out)

@router.get("/users", response_model=APIResponse)
async def list_users(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    users = UserRepository.get_all_users(limit=limit, offset=skip)
    data = [UserOut(
        id=u["user_id"],
        name=u["username"],
        phone=u["phone"],
        is_active=u["is_active"],
        created_at=u["created_at"]
    ) for u in users]
    return APIResponse(data=data)

@router.get("/users/{user_id}", response_model=APIResponse)
async def get_user(user_id: int):
    u = UserRepository.get_user_by_id(user_id)
    if not u:
        return APIResponse(code=404, message="用户不存在")
    return APIResponse(data=UserOut(
        id=u["user_id"],
        name=u["username"],
        phone=u["phone"],
        is_active=u["is_active"],
        created_at=u["created_at"]
    ))

@router.put("/users/{user_id}", response_model=APIResponse)
async def update_user_info(user_id: int, payload: UserUpdateRequest):
    try:
        success = UserRepository.update_user(
            user_id=user_id,
            username=payload.username,
            phone=payload.phone,
            extra_info=payload.extra_info
        )
    except Exception as e:
        if "UNIQUE" in str(e).upper():
            return APIResponse(code=409, message="手机号已被其他用户占用")
        logger.exception("更新用户失败")
        return APIResponse(code=500, message="更新失败")
    if not success:
        return APIResponse(code=404, message="用户不存在或未做修改")
    return APIResponse(message="更新成功")

class StatusToggle(BaseModel):
    is_active: int = Field(..., ge=0, le=1)

@router.put("/users/{user_id}/status", response_model=APIResponse)
async def toggle_user_status(user_id: int, body: StatusToggle):
    ok = UserRepository.update_user_status(user_id, body.is_active)
    if not ok:
        return APIResponse(code=404, message="用户不存在")
    return APIResponse(message="状态更新成功")

@router.delete("/users/{user_id}", response_model=APIResponse)
async def delete_user(user_id: int):
    try:
        AccessLogRepository.delete_logs_by_user_id(user_id)
        ok = UserRepository.hard_delete_user(user_id)
        if not ok:
            return APIResponse(code=404, message="用户不存在")
        try:
            app_state.remove_single_face_from_cache(user_id)
        except Exception:
            logger.exception("人脸缓存清理失败")
        return APIResponse(message="删除成功")
    except Exception as e:
        logger.exception("删除用户失败")
        return APIResponse(code=500, message=f"删除失败，可能存在关联数据：{str(e)}")

# ========================
# 包裹管理看板
# ========================
@router.get("/parcels", response_model=APIResponse)
async def get_parcels(
    status: Optional[int] = Query(None, ge=1, le=3, description="包裹状态过滤：1在库 2已取件 3异常"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取全量包裹列表，支持状态过滤与分页。
    收件人姓名通过手机号关联用户表展示真实姓名。
    """
    # 获取所有包裹（数据库层暂不支持状态过滤，此处先获取全量再过滤）
    parcels = ParcelRepository.get_all_parcels(limit=skip + limit + 100, offset=0)
    if status is not None:
        parcels = [p for p in parcels if p["status"] == status]

    # 分页切片
    page_parcels = parcels[skip: skip + limit]

    # 构建手机号->姓名映射
    phone_name_map = _build_user_phone_name_map()

    rdata = []
    for p in page_parcels:
        # 安全解析 extra_info
        extra = json.loads(p.get("extra_info") or "{}") if isinstance(p.get("extra_info"), str) else (p.get("extra_info") or {})
        receiver_phone = p["receiver_phone"]
        # 真实姓名优先从用户表获取，其次取 extra_info 中的字段（兼容旧数据）
        receiver_name = phone_name_map.get(receiver_phone, extra.get("receiver_name", "未知"))

        rdata.append(ParcelOut(
            id=p["parcel_id"],
            tracking_no=p["tracking_no"],
            company=extra.get("company", "未知"),
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            target_location=p["target_location"],
            cabinet_number=p.get("cabinet_number", ""),
            status=p["status"],
            in_time=p["in_time"],
            out_time=p.get("out_time")
        ))
    print(rdata)
    return APIResponse(data=rdata)


class ParcelCreateRequest(BaseModel):
    tracking_no: str = Field(..., min_length=1, max_length=100)
    receiver_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    cabinet_number: Optional[str] = Field("", max_length=20)
    company: Optional[str] = Field("未知", max_length=50)
    receiver_name: Optional[str] = Field("", max_length=50)
    target_location: Literal["A", "B"] = "A"
    status: Optional[int] = Field(1, ge=1, le=3)


class ParcelUpdateRequest(BaseModel):
    tracking_no: Optional[str] = Field(None, min_length=1, max_length=100)
    receiver_phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    cabinet_number: Optional[str] = Field(None, max_length=20)
    company: Optional[str] = Field(None, max_length=50)
    receiver_name: Optional[str] = Field(None, max_length=50)
    target_location: Optional[Literal["A", "B"]] = None
    status: Optional[int] = Field(None, ge=1, le=3)


@router.post("/parcels", response_model=APIResponse)
async def create_parcel(payload: ParcelCreateRequest):
    try:
        parcel_dict = ParcelRepository.add_parcel(
            tracking_no=payload.tracking_no,
            cabinet_number=payload.cabinet_number or "",
            receiver_phone=payload.receiver_phone,
            target_location=payload.target_location,
            status=payload.status,
            extra_info={"company": payload.company, "receiver_name": payload.receiver_name}
        )
    except RuntimeError as e:
        return APIResponse(code=400, message=f"入库失败：{str(e)}")
    except Exception as e:
        logger.exception("包裹入库异常")
        return APIResponse(code=500, message=f"系统异常：{str(e)}")

    return APIResponse(message="包裹入库成功", data={
        "parcel_id": parcel_dict["parcel_id"],
        "tracking_no": parcel_dict["tracking_no"],
        "cabinet_number": parcel_dict["cabinet_number"],
        "target_location": parcel_dict["target_location"],
    })


@router.get("/parcels/{parcel_id}", response_model=APIResponse)
async def get_parcel(parcel_id: int):
    p = ParcelRepository.get_parcel_by_id(parcel_id)
    if not p:
        return APIResponse(code=404, message="包裹不存在")
    extra = p.get("extra_info") or {}
    if isinstance(extra, str):
        extra = json.loads(extra)
    return APIResponse(data=ParcelOut(
        id=p["parcel_id"],
        tracking_no=p["tracking_no"],
        company=extra.get("company", "未知"),
        receiver_name=extra.get("receiver_name", "未知"),
        receiver_phone=p["receiver_phone"],
        target_location=p["target_location"],
        cabinet_number=p.get("cabinet_number", ""),
        status=p["status"],
        in_time=p["in_time"],
        out_time=p.get("out_time")
    ))


@router.put("/parcels/{parcel_id}", response_model=APIResponse)
async def update_parcel(parcel_id: int, payload: ParcelUpdateRequest):
    existing = ParcelRepository.get_parcel_by_id(parcel_id)
    if not existing:
        return APIResponse(code=404, message="包裹不存在")
    if payload.target_location is not None and existing["status"] != 1:
        return APIResponse(code=400, message="已取件或异常包裹不能修改目标类别")

    extra_info = existing.get("extra_info") or {}
    if isinstance(extra_info, str):
        extra_info = json.loads(extra_info)
    if payload.company is not None:
        extra_info["company"] = payload.company
    if payload.receiver_name is not None:
        extra_info["receiver_name"] = payload.receiver_name

    try:
        ok = ParcelRepository.update_parcel(
            parcel_id=parcel_id,
            tracking_no=payload.tracking_no,
            receiver_phone=payload.receiver_phone,
            cabinet_number=payload.cabinet_number,
            target_location=payload.target_location,
            status=payload.status,
            extra_info=extra_info if (payload.company is not None or payload.receiver_name is not None) else None
        )
    except Exception as e:
        logger.exception("更新包裹失败")
        return APIResponse(code=500, message=f"更新失败：{str(e)}")

    if not ok:
        return APIResponse(code=400, message="未做任何修改")
    return APIResponse(message="包裹信息已更新")


@router.delete("/parcels/{parcel_id}", response_model=APIResponse)
async def delete_parcel(parcel_id: int):
    ok = ParcelRepository.delete_parcel(parcel_id)
    if not ok:
        return APIResponse(code=404, message="包裹不存在或已删除")
    return APIResponse(message="包裹已删除")


# ========================
# 出入日志查询
# ========================
@router.get("/logs", response_model=APIResponse)
async def get_access_logs(
    action_type: Optional[str] = Query(None, pattern="^(IN|OUT)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """
    获取进出日志，支持按动作类型过滤与分页。
    注：当前数据库接口暂不支持服务器端过滤与偏移，路由层采用全量加载后过滤切片，数据量大时需优化。
    """
    # 获取足够多的原始日志（假设按时间倒序）
    raw_logs = AccessLogRepository.get_recent_logs(limit=1000)  # 一次性拉取，简单方案
    if action_type:
        raw_logs = [log for log in raw_logs if log.get("action_type") == action_type]

    # 分页
    page_logs = raw_logs[skip: skip + limit]

    data = []
    for log in page_logs:
        data.append(AccessLogOut(
            id=log["log_id"],
            user_id=log["user_id"],
            user_name=log.get("username", "未知"),
            user_phone=log.get("phone", ""),
            action_type=log["action_type"],
            snapshot_path=log.get("snapshot_path", ""),
            picked_parcels=json.dumps(log.get("picked_parcels")) if isinstance(log.get("picked_parcels"), list) else log.get("picked_parcels"),
            created_at=log.get("timestamp", "")
        ))
    return APIResponse(data=data)
