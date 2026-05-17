from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import cv2
import logging

from core.state import app_state
from database.models import ParcelRepository
from database.schemas import APIResponse, ScanResultData

logger = logging.getLogger("SmartStation")
router = APIRouter(prefix="/station", tags=["Station Operations"])


@router.post("/scan_in", response_model=APIResponse)
async def scan_and_store():
    """
    快递员放置包裹，触发摄像头抓拍并扫码入库。
    系统自动分配货柜号，取件码即为货柜号。
    """
    # 1. 获取货物摄像头帧（与人脸共用摄像头，后续前端应赋予入库扫描更高优先级）
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    # 2. 调用 QRScanner 解码
    if not app_state.scanner:
        return APIResponse(code=500, message="扫描器未就绪")
    annotated_frame, qr_data_list = app_state.scanner.scan(frame)

    if not qr_data_list:
        return APIResponse(code=400, message="未检测到有效条码/二维码")

    # 3. 提取并校验关键字段（假设每帧仅处理首个条码）
    qr_data = qr_data_list[0]
    tracking_no = qr_data.get("tracking_no")
    receiver_phone = qr_data.get("receiver_phone")

    if not tracking_no or not receiver_phone or tracking_no == "UNKNOWN_NO":
        return APIResponse(code=400, message="二维码数据不完整，缺少快递单号或收件人手机号")
    if receiver_phone == "UNKNOWN_PHONE":
        return APIResponse(code=400, message="二维码中未包含有效收件人手机号")

    company = qr_data.get("company", "未知")
    receiver_name = qr_data.get("receiver_name", "未知")

    # 4. 入库并自动分配货柜号
    try:
        parcel_dict = ParcelRepository.add_parcel(
            tracking_no=tracking_no,
            receiver_phone=receiver_phone,
            extra_info={"company": company, "receiver_name": receiver_name}
        )
    except RuntimeError as e:
        # 例如柜满等异常
        return APIResponse(code=400, message=f"入库失败：{str(e)}")
    except Exception as e:
        logger.error(f"包裹入库异常: {e}")
        return APIResponse(code=500, message=f"系统入库异常：{str(e)}")

    # 5. 组装返回数据（取件码即 cabinet_number）
    result_data = ScanResultData(
        tracking_no=tracking_no,
        company=company,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        cabinet_number=parcel_dict["cabinet_number"],
        is_new_user=False
    )

    return APIResponse(message="入库成功", data=result_data)


async def generate_mjpeg_stream(camera_instance):
    """MJPEG 视频流生成器，用于实时监控"""
    while True:
        success, frame = camera_instance.get_frame()
        if success:
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        await asyncio.sleep(0.03)


@router.get("/video_feed")
async def station_video_feed():
    """驿站端货物监控视频流（与人脸共用摄像头）"""
    return StreamingResponse(
        generate_mjpeg_stream(app_state.camera),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )