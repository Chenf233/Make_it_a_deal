from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import cv2

from core.state import app_state
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.schemas import APIResponse, FaceAuthResult, UserOut, ParcelOut

router = APIRouter(prefix="/client", tags=["Client Experience"])

@router.post("/access/entry", response_model=APIResponse)
async def client_entry():
    """
    客户刷脸进门：抓图 -> 1:N 检索 -> 模拟开门 -> 返回包裹列表
    """
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    embedding = app_state.face_recognizer.extract_feature(frame)
    if embedding is None:
        return APIResponse(code=400, message="未检测到人脸，请正对摄像头")

    # 极速内存检索 (假设阈值 0.5)
    user_id = app_state.search_face(embedding, threshold=0.5)
    if not user_id:
        return APIResponse(code=401, message="识别失败：您未在系统中录入")

    # 查询用户信息
    user = AccessLogRepository.add_log(
        user_id=user_id, 
        action_type="IN", 
        snapshot_path="", 
        picked_parcels=",".join([p.tracking_no for p in parcels]) # 存单号逗号分隔
    )
    if not user:
        return APIResponse(code=404, message="用户数据异常")

    # 查询名下在库包裹
    parcels = ParcelRepository.get_active_parcels_by_phone(user.phone)
    
    # 转换为 Schema 输出对象
    user_out = UserOut(
        id=user.id, name=user.name, phone=user.phone, 
        is_active=user.is_active, created_at=user.created_at
    )
    parcel_outs =[
        ParcelOut(
            id=p.id, tracking_no=p.tracking_no, company=p.company, 
            receiver_name=p.receiver_name, receiver_phone=p.receiver_phone, 
            status=p.status, in_time=p.in_time, out_time=p.out_time
        ) for p in parcels
    ]

    # 记录日志
    AccessLogRepository.add_log(log_type="ENTRY", user_id=user_id, details=f"刷脸进门，待取包裹: {len(parcels)}件")

    # WebSocket 触发前端硬件/弹窗
    if hasattr(app_state, "trigger_hardware_alert"):
        await app_state.trigger_hardware_alert(
            action_type="DOOR_OPEN", 
            payload={"msg": f"欢迎 {user.name}，您有 {len(parcels)} 个包裹待取"}
        )

    # 组装聚合返回数据
    result = FaceAuthResult(
        user=user_out,
        active_parcels=parcel_outs,
        action="IN",
        has_forgotten_parcels=False
    )
    
    return APIResponse(message="验证通过，已开门", data=result)

@router.post("/access/exit", response_model=APIResponse)
async def client_exit():
    """
    客户刷脸出门：验证身份 -> 校验是否拿完 -> 关门
    """
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
    
    # 出门时复查在库包裹
    parcels = ParcelRepository.get_active_parcels_by_phone(user.phone)
    has_forgotten = len(parcels) > 0

    if has_forgotten and hasattr(app_state, "trigger_hardware_alert"):
        await app_state.trigger_hardware_alert(
            action_type="FORGET_ALERT", 
            payload={"msg": f"警报：{user.name} 遗漏了 {len(parcels)} 个包裹未取走！"}
        )

    AccessLogRepository.add_log(log_type="EXIT", user_id=user_id, details="刷脸出门")

    user_out = UserOut(
        id=user.id, name=user.name, phone=user.phone, 
        is_active=user.is_active, created_at=user.created_at
    )
    parcel_outs =[
        ParcelOut(
            id=p.id, tracking_no=p.tracking_no, company=p.company, 
            receiver_name=p.receiver_name, receiver_phone=p.receiver_phone, 
            status=p.status, in_time=p.in_time, out_time=p.out_time
        ) for p in parcels
    ]
    
    result = FaceAuthResult(
        user=user_out,
        active_parcels=parcel_outs,
        action="OUT",
        has_forgotten_parcels=has_forgotten
    )

    return APIResponse(message="检测到遗漏包裹" if has_forgotten else "出门成功，门已开", data=result)

async def generate_mjpeg_stream(camera_instance):
    """通用的 MJPEG 视频流生成器"""
    while True:
        success, frame = camera_instance.get_frame()
        if success:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03)

@router.get("/video_feed")
async def client_video_feed():
    """客户端人脸预览视频流"""
    return StreamingResponse(
        generate_mjpeg_stream(app_state.camera),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )