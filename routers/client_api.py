from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import cv2
import json
import logging

from core.state import app_state
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.schemas import APIResponse, FaceAuthResult, UserOut, ParcelOut
from services.face_recognition.constants import SIMILARITY_THRESHOLD
from services.hardware_manager import lock_user_cabinets, open_user_cabinets
from services.pickup import PickupHandler

router = APIRouter(prefix="/client", tags=["Client Experience"])
logger = logging.getLogger("SmartStation")

pickup_handler = PickupHandler()


def build_parcel_out(p: dict) -> ParcelOut:
    """内部辅助函数：将数据库包裹字典映射为 ParcelOut 响应模型"""
    extra = p.get("extra_info") or {}
    if isinstance(extra, str):
        extra = json.loads(extra)
    return ParcelOut(
        id=p["parcel_id"],
        tracking_no=p["tracking_no"],
        company=extra.get("company", "未知"),
        receiver_name=extra.get("receiver_name", "未知"),
        receiver_phone=p["receiver_phone"],
        target_location=p["target_location"],
        cabinet_number=p["cabinet_number"],   # 修复：之前遗漏此字段
        status=p["status"],
        in_time=p["in_time"],
        out_time=p["out_time"]
    )


@router.post("/access/auth", response_model=APIResponse)
async def client_auth(intent: str | None = None):
    """刷脸认证：可通过 intent 限制本次操作为进门或出门"""
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    embedding = await asyncio.get_event_loop().run_in_executor(
        None, app_state.face_recognizer.extract_feature, frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸，请正对摄像头")

    user_id = app_state.search_face(embedding, threshold=SIMILARITY_THRESHOLD)
    if not user_id:
        return APIResponse(code=401, message="识别失败：您未在系统中录入")

    user = UserRepository.get_user_by_id(user_id)
    if not user:
        return APIResponse(code=404, message="用户数据异常")
    elif not user.get("is_active"):
        return APIResponse(code=401, message="您的账户已被禁用，请联系管理员")

    user_out = UserOut(
        id=user["user_id"],
        name=user["username"],
        phone=user["phone"],
        is_active=user["is_active"],
        created_at=user["created_at"]
    )

    last_action = AccessLogRepository.get_last_action(user_id, action_types=['IN', 'OUT'])
    requested_intent = intent.lower() if intent else None
    if requested_intent not in (None, "entry", "exit"):
        return APIResponse(code=400, message="无效的刷脸操作类型")

    if last_action == "IN":
        if requested_intent == "entry":
            return APIResponse(code=409, message="您已在站内，请点击刷脸出门")

        # ---- 出门模式 ----
        status = pickup_handler.check_exit_status(user_id)
        result = FaceAuthResult(
            user=user_out,
            active_parcels=[build_parcel_out(p) for p in status["active_parcels"]],
            action="EXIT",
            has_forgotten_parcels=len(status["active_parcels"]) > 0,
            exit_expected_total=status["expected_total"],
            exit_picked_count=status["picked_count"]
        )
        return APIResponse(message="请确认取件情况", data=result)
    else:
        if requested_intent == "exit":
            return APIResponse(code=409, message="您当前不在站内，请先刷脸入门")

        # ---- 进门模式 ----
        parcels = ParcelRepository.get_active_parcels_by_phone(user["phone"])
        parcel_outs = [build_parcel_out(p) for p in parcels]

        AccessLogRepository.add_log(
            user_id=user_id,
            action_type="IN",
            snapshot_path="",
            picked_parcels=[p["tracking_no"] for p in parcels]
        )

        cabinet_numbers = [p["cabinet_number"] for p in parcels if p.get("cabinet_number")]
        if cabinet_numbers:
            try:
                open_user_cabinets(user_id, cabinet_numbers)
            except Exception:
                logger.exception("Failed to open cabinets for user %s", user_id)

        if hasattr(app_state, "trigger_hardware_alert"):
            await app_state.trigger_hardware_alert(
                action_type="CABINET_UNLOCK",
                payload={"msg": f"欢迎 {user['username']}，您有 {len(parcels)} 个包裹待取"}
            )

        result = FaceAuthResult(
            user=user_out,
            active_parcels=parcel_outs,
            action="ENTRY",
            has_forgotten_parcels=False
        )
        return APIResponse(message="验证通过", data=result)


@router.post("/access/exit_confirm", response_model=APIResponse)
async def client_exit_confirm():
    """用户确认出门：记录 OUT 日志并锁门"""
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    embedding = await asyncio.get_event_loop().run_in_executor(
        None, app_state.face_recognizer.extract_feature, frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸")

    user_id = app_state.search_face(embedding, threshold=SIMILARITY_THRESHOLD)
    if not user_id:
        return APIResponse(code=401, message="识别失败")

    user = UserRepository.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return APIResponse(code=401, message="用户状态异常")

    AccessLogRepository.add_log(
        user_id=user_id,
        action_type="OUT",
        snapshot_path="",
        picked_parcels=[]
    )

    try:
        lock_user_cabinets(user_id)
    except Exception:
        logger.exception("Failed to lock cabinets for user %s", user_id)

    if hasattr(app_state, "trigger_hardware_alert"):
        await app_state.trigger_hardware_alert(
            action_type="CABINET_LOCK",
            payload={"msg": f"再见 {user['username']}，门已关闭"}
        )

    return APIResponse(message="出门成功")


@router.post("/confirm_pickup", response_model=APIResponse)
async def confirm_pickup():
    """
    客户在站内扫描包裹 QR 码确认取件。
    不依赖前端 user_id，人脸识别后自动推断身份。
    """
    success, msg, parcel_info = await pickup_handler.handle_pickup()
    if not success:
        return APIResponse(code=400, message=msg)
    return APIResponse(message=msg, data=parcel_info)


async def generate_mjpeg_stream(camera_instance, fps: int = 30):
    interval = 1.0 / fps
    try:
        while True:
            t0 = asyncio.get_event_loop().time()
            success, frame = camera_instance.get_frame()
            if success:
                _, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(0, interval - elapsed))
    except asyncio.CancelledError:
        pass


@router.get("/video_feed")
async def client_video_feed():
    return StreamingResponse(
        generate_mjpeg_stream(app_state.camera),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
