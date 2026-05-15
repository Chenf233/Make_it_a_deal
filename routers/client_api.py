from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import cv2
import json

from core.state import app_state
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.schemas import APIResponse, FaceAuthResult, UserOut, ParcelOut

router = APIRouter(prefix="/client", tags=["Client Experience"])

def build_parcel_out(p: dict) -> ParcelOut:
    """内部辅助函数：处理数据库字典与 Schema 的映射"""
    extra = json.loads(p.get("extra_info") or "{}")
    return ParcelOut(
        id=p["parcel_id"],
        tracking_no=p["tracking_no"],
        company=extra.get("company", "未知"),
        receiver_name=extra.get("receiver_name", "未知"),
        receiver_phone=p["receiver_phone"],
        status=p["status"],
        in_time=p["in_time"],
        out_time=p["out_time"]
    )

@router.post("/access/entry", response_model=APIResponse)
async def client_entry():
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    embedding = app_state.face_recognizer.extract_feature(frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸，请正对摄像头")

    user_id = app_state.search_face(embedding, threshold=0.5)
    if not user_id:
        return APIResponse(code=401, message="识别失败：您未在系统中录入")

    user = UserRepository.get_user_by_id(user_id)
    if not user:
        return APIResponse(code=404, message="用户数据异常")
    elif not user.get("is_active"):
        return APIResponse(code=401, message="您的账户已被禁用，请联系管理员")

    # 修复：数据库字典映射到 UserOut
    user_out = UserOut(
        id=user["user_id"], 
        name=user["username"], 
        phone=user["phone"], 
        is_active=user["is_active"], 
        created_at=user["created_at"]
    )

    parcels = ParcelRepository.get_active_parcels_by_phone(user["phone"])
    parcel_outs = [build_parcel_out(p) for p in parcels]

    AccessLogRepository.add_log(
        user_id=user_id, 
        action_type="IN", 
        snapshot_path="", 
        picked_parcels=[p["tracking_no"] for p in parcels]
    )

    if hasattr(app_state, "trigger_hardware_alert"):
        await app_state.trigger_hardware_alert(
            action_type="DOOR_OPEN", 
            payload={"msg": f"欢迎 {user['username']}，您有 {len(parcels)} 个包裹待取"}
        )

    result = FaceAuthResult(
        user=user_out, active_parcels=parcel_outs, action="IN", has_forgotten_parcels=False
    )
    return APIResponse(message="验证通过，已开门", data=result)

@router.post("/access/exit", response_model=APIResponse)
async def client_exit():
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    embedding = app_state.face_recognizer.extract_feature(frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸")

    user_id = app_state.search_face(embedding, threshold=0.5)
    if not user_id:
        return APIResponse(code=401, message="识别失败")

    user = UserRepository.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return APIResponse(code=401, message="您的账户已被禁用，请联系管理员")
    
    parcels = ParcelRepository.get_active_parcels_by_phone(user["phone"])
    for p in parcels:
        ParcelRepository.update_parcel_status(p["parcel_id"], 2)   # 状态 2 = 已取件

    has_forgotten = len(parcels) > 0

    if has_forgotten and hasattr(app_state, "trigger_hardware_alert"):
        await app_state.trigger_hardware_alert(
            action_type="FORGET_ALERT", 
            payload={"msg": f"警报：{user['username']} 遗漏了 {len(parcels)} 个包裹未取走！"}
        )

    AccessLogRepository.add_log(
        user_id=user_id, 
        action_type="OUT", 
        snapshot_path="", 
        picked_parcels=[p["tracking_no"] for p in parcels]
    )

    user_out = UserOut(
        id=user["user_id"], name=user["username"], phone=user["phone"], 
        is_active=user["is_active"], created_at=user["created_at"]
    )
    parcel_outs =[build_parcel_out(p) for p in parcels]
    
    result = FaceAuthResult(
        user=user_out, active_parcels=parcel_outs, action="OUT", has_forgotten_parcels=has_forgotten
    )
    return APIResponse(message="检测到遗漏包裹" if has_forgotten else "出门成功，门已开", data=result)

async def generate_mjpeg_stream(camera_instance):
    while True:
        success, frame = camera_instance.get_frame()
        if success:
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        await asyncio.sleep(0.03)

@router.get("/video_feed")
async def client_video_feed():
    return StreamingResponse(
        generate_mjpeg_stream(app_state.camera), media_type="multipart/x-mixed-replace; boundary=frame"
    )