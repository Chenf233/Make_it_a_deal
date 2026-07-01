from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio
import cv2
import logging

from core.state import app_state
from database.models import ParcelRepository
from database.schemas import APIResponse, ScanResultData
from services.motor import half_turn, half_turn2, start_continuous, stop_continuous, rotate_turns, motor3_cw, motor3_ccw
from services.BuzzerLight import start_loop, stop_loop, BUZZER1_PIN, BUZZER2_PIN
from services.scanner.constants import DEMO_DATA_LIST

logger = logging.getLogger("SmartStation")
router = APIRouter(prefix="/station", tags=["Station Operations"])


@router.post("/scan_in", response_model=APIResponse)
async def scan_and_store():
    success, frame = app_state.camera.get_frame()
    if not success or frame is None:
        return APIResponse(code=500, message="摄像头抓图失败")

    if not app_state.scanner:
        return APIResponse(code=500, message="扫描器未就绪")
    annotated_frame, qr_data_list = app_state.scanner.scan(frame)

    if not qr_data_list:
        return APIResponse(code=400, message="未检测到有效条码/二维码")

    qr_data = qr_data_list[0]
    tracking_no = qr_data.get("tracking_no")
    receiver_phone = qr_data.get("receiver_phone")

    if not tracking_no or not receiver_phone or tracking_no == "UNKNOWN_NO":
        return APIResponse(code=400, message="二维码数据不完整，缺少快递单号或收件人手机号")
    if receiver_phone == "UNKNOWN_PHONE":
        return APIResponse(code=400, message="二维码中未包含有效收件人手机号")

    company = qr_data.get("company", "未知")
    receiver_name = qr_data.get("receiver_name", "未知")

    try:
        parcel_dict = ParcelRepository.add_parcel(
            tracking_no=tracking_no,
            receiver_phone=receiver_phone,
            extra_info={"company": company, "receiver_name": receiver_name}
        )
    except RuntimeError as e:
        return APIResponse(code=400, message=f"入库失败：{str(e)}")
    except Exception as e:
        logger.error(f"扫描入库异常: {e}")
        return APIResponse(code=500, message=f"系统内部异常：{str(e)}")

    result_data = ScanResultData(
        tracking_no=tracking_no,
        company=company,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        cabinet_number=parcel_dict["cabinet_number"],
        is_new_user=False
    )

    return APIResponse(message="入库成功", data=result_data)


@router.post("/move_to_a02", response_model=APIResponse)
async def move_to_a02():
    try:
        await asyncio.sleep(15)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, rotate_turns, 2, 0, 20)
        await loop.run_in_executor(None, motor3_cw, 10)
        await loop.run_in_executor(None, rotate_turns, 2, 1, 20)

        data = DEMO_DATA_LIST[0]
        parcel_dict = ParcelRepository.add_parcel(
            tracking_no=data["tracking_no"],
            receiver_phone=data["receiver_phone"],
            cabinet_number="A02",
            extra_info={"company": data["company"], "receiver_name": data["receiver_name"]}
        )

        return APIResponse(
            message=f"快捷操作完成：电机2左旋20圈→电机3顺时针10秒→电机2右旋20圈，已入库 {data['tracking_no']}",
            data=parcel_dict
        )
    except Exception as e:
        logger.exception("快捷操作失败")
        return APIResponse(code=500, message=f"快捷操作失败：{str(e)}")


async def generate_mjpeg_stream(camera_instance):
    while True:
        success, frame = camera_instance.get_frame()
        if success:
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        await asyncio.sleep(0.03)


@router.post("/motor/left")
async def motor_left():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, half_turn, 0)
    return APIResponse(message="电机1下降半圈完成")


@router.post("/motor/right")
async def motor_right():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, half_turn, 1)
    return APIResponse(message="电机1上升半圈完成")


@router.post("/motor2/left")
async def motor2_left():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, half_turn2, 0)
    return APIResponse(message="电机2左旋半圈完成")


@router.post("/motor2/right")
async def motor2_right():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, half_turn2, 1)
    return APIResponse(message="电机2右旋半圈完成")


@router.post("/motor/left/start")
async def motor_left_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_continuous, 1, 0)
    return APIResponse(message="电机1开始下降连续")


@router.post("/motor/left/stop")
async def motor_left_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_continuous, 1)
    return APIResponse(message="电机1已停止")


@router.post("/motor/right/start")
async def motor_right_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_continuous, 1, 1)
    return APIResponse(message="电机1开始上升连续")


@router.post("/motor/right/stop")
async def motor_right_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_continuous, 1)
    return APIResponse(message="电机1已停止")


@router.post("/motor2/left/start")
async def motor2_left_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_continuous, 2, 0)
    return APIResponse(message="电机2开始左旋连续")


@router.post("/motor2/left/stop")
async def motor2_left_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_continuous, 2)
    return APIResponse(message="电机2已停止")


@router.post("/motor2/right/start")
async def motor2_right_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_continuous, 2, 1)
    return APIResponse(message="电机2开始右旋连续")


@router.post("/motor2/right/stop")
async def motor2_right_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_continuous, 2)
    return APIResponse(message="电机2已停止")


@router.post("/motor3/cw")
async def motor3_cw_endpoint():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, motor3_cw, 5)
    return APIResponse(message="电机3顺时针旋转5秒完成")


@router.post("/motor3/ccw")
async def motor3_ccw_endpoint():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, motor3_ccw, 5)
    return APIResponse(message="电机3逆时针旋转5秒完成")


@router.post("/buzzer/1/start")
async def buzzer1_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_loop, BUZZER2_PIN)
    return APIResponse(message="蜂鸣器1开始循环")


@router.post("/buzzer/1/stop")
async def buzzer1_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_loop, BUZZER2_PIN)
    return APIResponse(message="蜂鸣器1已停止")


@router.post("/buzzer/2/start")
async def buzzer2_start():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_loop, BUZZER1_PIN)
    return APIResponse(message="蜂鸣器2开始循环")


@router.post("/buzzer/2/stop")
async def buzzer2_stop():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, stop_loop, BUZZER1_PIN)
    return APIResponse(message="蜂鸣器2已停止")


@router.get("/video_feed")
async def station_video_feed():
    return StreamingResponse(
        generate_mjpeg_stream(app_state.camera),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
