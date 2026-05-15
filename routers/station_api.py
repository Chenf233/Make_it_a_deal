from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import cv2

from core.state import app_state
from database.models import ParcelRepository, AccessLogRepository
from database.schemas import APIResponse, ScanResultData

router = APIRouter(prefix="/station", tags=["Station Operations"])

@router.post("/scan_in", response_model=APIResponse)
async def scan_and_store():
    """
    快递员放置包裹，触发摄像头抓拍并扫码入库
    """
    # 1. 获取当前货物摄像头帧 (假设挂载在 app_state.camera)
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    # 2. 调用全局实例 scanner 进行解析
    # 根据 scanner 文档，返回值为: 绘制后的图, 字典列表
    annotated_frame, qr_data_list = app_state.scanner.scan(frame)
    
    if not qr_data_list:
        return APIResponse(code=400, message="未检测到有效条码/二维码")

    # 3. 提取解析数据（假设提取画面中第一个二维码字典）
    qr_data = qr_data_list[0]
    
    # 假设二维码解出来的 JSON 字典里包含 tracking_no, company, receiver_phone 等字段
    # 如果实际只有单号字符串，可以改为 qr_data.get("data")，这里配合 ScanResultData 结构
    tracking_no = qr_data.get("tracking_no", "UNKNOWN_NO")
    company = qr_data.get("company", "UNKNOWN_COMP")
    receiver_name = qr_data.get("receiver_name", "UNKNOWN_NAME")
    receiver_phone = qr_data.get("receiver_phone", "UNKNOWN_PHONE")

    # 4. 业务入库
    try:
        # 使用真实的 DAO 参数
        ParcelRepository.add_parcel(
            tracking_no=tracking_no, 
            pickup_code=tracking_no[-6:],  # 模拟取件码：截取单号后6位（或者由独立逻辑生成）
            receiver_phone=receiver_phone,
            status=1,
            extra_info={"company": company, "receiver_name": receiver_name} # 额外信息塞入 dict
        )
    except Exception as e:
        return APIResponse(code=400, message=f"入库失败，可能是单号已存在: {str(e)}")

    # 5. 组装返回给前端展示的数据结构
    result_data = ScanResultData(
        tracking_no=tracking_no,
        company=company,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        is_new_user=False # 根据业务逻辑判断，这里暂设False
    )

    return APIResponse(message="入库成功", data=result_data)

async def generate_mjpeg_stream(camera_instance):
    """通用的 MJPEG 视频流生成器"""
    while True:
        success, frame = camera_instance.get_frame()
        if success:
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03) # 限制约 30 FPS

@router.get("/video_feed")
async def station_video_feed():
    """驿站端货物监控视频流"""
    return StreamingResponse(
        generate_mjpeg_stream(app_state.cargo_camera),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )