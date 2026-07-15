from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import cv2
import logging
import time
import uuid

from core.state import app_state
from database.models import ParcelRepository
from database.schemas import APIResponse, ScanResultData
from services.motor import half_turn, half_turn2, start_continuous, stop_continuous, rotate_turns, motor3_cw, motor3_ccw
from services.BuzzerLight import start_loop, stop_loop, BUZZER1_PIN, BUZZER2_PIN
from services.scanner.constants import DEMO_DATA_LIST

logger = logging.getLogger("SmartStation")
router = APIRouter(prefix="/station", tags=["Station Operations"])

STATION_INBOUND_LOCK = asyncio.Lock()
SCAN_IN_WINDOW_SECONDS = 10
SCAN_IN_INTERVAL_SECONDS = 0.2
PENDING_INBOUND_TTL_SECONDS = 120
PENDING_INBOUND_TASKS = {}

# 机械臂初始位置按 A01/B01 对齐。调参时只需要改这里。
# motor2_right_turns: 从左到右移动；motor1_down_turns: 从上到下移动。
# A/B 两面目前只通过 motor3_direction 区分投递方向。
CABINET_MOVE_PARAMS = {
    "A01": {"motor2_right_turns": 0, "motor1_down_turns": 0, "motor3_direction": "cw", "motor3_seconds": 10},
    "A02": {"motor2_right_turns": 20, "motor1_down_turns": 0, "motor3_direction": "cw", "motor3_seconds": 10},
    "A03": {"motor2_right_turns": 0, "motor1_down_turns": 13, "motor3_direction": "cw", "motor3_seconds": 10},
    "A04": {"motor2_right_turns": 20, "motor1_down_turns": 13, "motor3_direction": "cw", "motor3_seconds": 10},
    "B01": {"motor2_right_turns": 0, "motor1_down_turns": 0, "motor3_direction": "ccw", "motor3_seconds": 10},
    "B02": {"motor2_right_turns": 20, "motor1_down_turns": 0, "motor3_direction": "ccw", "motor3_seconds": 10},
    "B03": {"motor2_right_turns": 0, "motor1_down_turns": 13, "motor3_direction": "ccw", "motor3_seconds": 10},
    "B04": {"motor2_right_turns": 20, "motor1_down_turns": 13, "motor3_direction": "ccw", "motor3_seconds": 10},
}


async def move_parcel_to_cabinet(cabinet_number: str):
    params = CABINET_MOVE_PARAMS.get(cabinet_number)
    if not params:
        raise RuntimeError(f"柜号 {cabinet_number} 暂未配置机械臂路径")

    loop = asyncio.get_event_loop()
    motor2_right_turns = params["motor2_right_turns"]
    motor1_down_turns = params["motor1_down_turns"]

    if motor2_right_turns:
        await loop.run_in_executor(None, rotate_turns, 2, 0, motor2_right_turns)
    if motor1_down_turns:
        await loop.run_in_executor(None, rotate_turns, 1, 0, motor1_down_turns)

    motor3_direction = params["motor3_direction"]
    motor3_seconds = params["motor3_seconds"]
    if motor3_direction == "cw":
        await loop.run_in_executor(None, motor3_cw, motor3_seconds)
    elif motor3_direction == "ccw":
        await loop.run_in_executor(None, motor3_ccw, motor3_seconds)
    else:
        raise RuntimeError(f"柜号 {cabinet_number} 的 motor3_direction 配置无效")

    if motor1_down_turns:
        await loop.run_in_executor(None, rotate_turns, 1, 1, motor1_down_turns)
    if motor2_right_turns:
        await loop.run_in_executor(None, rotate_turns, 2, 1, motor2_right_turns)


def build_scan_result(qr_data: dict, parcel_dict: dict) -> ScanResultData:
    return ScanResultData(
        tracking_no=qr_data["tracking_no"],
        company=qr_data.get("company", "未知"),
        receiver_name=qr_data.get("receiver_name", "未知"),
        receiver_phone=qr_data["receiver_phone"],
        cabinet_number=parcel_dict["cabinet_number"],
        is_new_user=False
    )


def build_preview_data(token: str, qr_data: dict, cabinet_number: str) -> dict:
    return {
        "token": token,
        "tracking_no": qr_data["tracking_no"],
        "company": qr_data.get("company", "未知"),
        "receiver_name": qr_data.get("receiver_name", "未知"),
        "receiver_phone": qr_data["receiver_phone"],
        "cabinet_number": cabinet_number,
    }


def cleanup_pending_inbound_tasks():
    now = time.time()
    expired_tokens = [
        token for token, task in PENDING_INBOUND_TASKS.items()
        if now - task["created_at"] > PENDING_INBOUND_TTL_SECONDS
    ]
    for token in expired_tokens:
        PENDING_INBOUND_TASKS.pop(token, None)


def get_pending_cabinet_numbers(exclude_token: str | None = None) -> set:
    cleanup_pending_inbound_tasks()
    return {
        task["cabinet_number"]
        for token, task in PENDING_INBOUND_TASKS.items()
        if token != exclude_token
    }


def validate_inbound_qr(qr_data: dict) -> APIResponse | None:
    tracking_no = qr_data.get("tracking_no")
    receiver_phone = qr_data.get("receiver_phone")

    if not tracking_no or not receiver_phone or tracking_no == "UNKNOWN_NO":
        return APIResponse(code=400, message="二维码数据不完整，缺少快递单号或收件人手机号")
    if receiver_phone == "UNKNOWN_PHONE":
        return APIResponse(code=400, message="二维码中未包含有效收件人手机号")
    return None


def create_parcel_from_qr(qr_data: dict, cabinet_number: str) -> dict:
    return ParcelRepository.add_parcel(
        tracking_no=qr_data["tracking_no"],
        receiver_phone=qr_data["receiver_phone"],
        cabinet_number=cabinet_number,
        status=1,
        extra_info={
            "company": qr_data.get("company", "未知"),
            "receiver_name": qr_data.get("receiver_name", "未知"),
            "qr_status": qr_data.get("status"),
            "qr_in_time": qr_data.get("in_time")
        }
    )


async def scan_inbound_qr(request: Request) -> APIResponse | dict:
    if not app_state.camera:
        return APIResponse(code=500, message="摄像头未就绪")
    if not app_state.scanner:
        return APIResponse(code=500, message="扫描器未就绪")

    loop = asyncio.get_event_loop()
    deadline = loop.time() + SCAN_IN_WINDOW_SECONDS
    last_camera_error = False

    while loop.time() < deadline:
        if await request.is_disconnected():
            return APIResponse(code=499, message="扫码已取消")

        success, frame = app_state.camera.get_frame()
        if not success or frame is None:
            last_camera_error = True
            await asyncio.sleep(SCAN_IN_INTERVAL_SECONDS)
            continue

        last_camera_error = False
        _, qr_data_list = app_state.scanner.scan(frame)
        if qr_data_list:
            return qr_data_list[0]

        await asyncio.sleep(SCAN_IN_INTERVAL_SECONDS)

    if last_camera_error:
        return APIResponse(code=500, message="摄像头抓图失败")
    return APIResponse(code=400, message=f"{SCAN_IN_WINDOW_SECONDS} 秒内未检测到有效条码/二维码")


@router.post("/scan_in/preview", response_model=APIResponse)
async def preview_scan_in(request: Request):
    qr_result = await scan_inbound_qr(request)
    if isinstance(qr_result, APIResponse):
        return qr_result

    qr_data = qr_result
    invalid_response = validate_inbound_qr(qr_data)
    if invalid_response:
        return invalid_response

    async with STATION_INBOUND_LOCK:
        try:
            tracking_no = qr_data["tracking_no"]
            if ParcelRepository.get_parcel_by_tracking_no(tracking_no):
                return APIResponse(code=400, message=f"入库失败：快递单号 {tracking_no} 已存在")

            cabinet_number = ParcelRepository.allocate_cabinet(
                set(CABINET_MOVE_PARAMS) - get_pending_cabinet_numbers()
            )
            token = uuid.uuid4().hex
            PENDING_INBOUND_TASKS[token] = {
                "qr_data": qr_data,
                "cabinet_number": cabinet_number,
                "created_at": time.time(),
            }
        except RuntimeError as e:
            return APIResponse(code=400, message=f"预分配失败：{str(e)}")
        except Exception as e:
            logger.exception("扫码预览异常")
            return APIResponse(code=500, message=f"系统内部异常：{str(e)}")

    return APIResponse(message="扫码成功，请确认入库", data=build_preview_data(token, qr_data, cabinet_number))


@router.post("/scan_in/confirm", response_model=APIResponse)
async def confirm_scan_in(payload: dict):
    token = payload.get("token") if isinstance(payload, dict) else None
    if not token:
        return APIResponse(code=400, message="缺少入库确认 token")

    async with STATION_INBOUND_LOCK:
        cleanup_pending_inbound_tasks()
        task = PENDING_INBOUND_TASKS.get(token)
        if not task:
            return APIResponse(code=400, message="入库确认已过期，请重新扫码")

        qr_data = task["qr_data"]
        cabinet_number = task["cabinet_number"]

        try:
            tracking_no = qr_data["tracking_no"]
            if ParcelRepository.get_parcel_by_tracking_no(tracking_no):
                PENDING_INBOUND_TASKS.pop(token, None)
                return APIResponse(code=400, message=f"入库失败：快递单号 {tracking_no} 已存在")

            if cabinet_number in ParcelRepository.get_active_cabinet_numbers():
                PENDING_INBOUND_TASKS.pop(token, None)
                return APIResponse(code=400, message=f"入库失败：预分配货柜 {cabinet_number} 已被占用，请重新扫码")

            await move_parcel_to_cabinet(cabinet_number)
            parcel_dict = create_parcel_from_qr(qr_data, cabinet_number)
            PENDING_INBOUND_TASKS.pop(token, None)
        except RuntimeError as e:
            return APIResponse(code=400, message=f"入库失败：{str(e)}")
        except Exception as e:
            logger.exception("确认入库异常")
            return APIResponse(code=500, message=f"系统内部异常：{str(e)}")

    return APIResponse(message=f"入库成功：已分配 {parcel_dict['cabinet_number']}", data=build_scan_result(qr_data, parcel_dict))


@router.post("/scan_in", response_model=APIResponse)
async def scan_and_store(request: Request):
    return await preview_scan_in(request)


@router.post("/move_to_a02", response_model=APIResponse)
async def move_to_a02():#注：目前演示只做了移动到某一特定柜前，期末考实在是等不住了，今天7月4号还在写文档
    try:                #7月6号开始考期末考，还是一点都没开始复习，实际初赛的时候将会完善这一段一键入库的代码
        await asyncio.sleep(5)
        await move_parcel_to_cabinet("A02")

        data = DEMO_DATA_LIST[0]
        parcel_dict = ParcelRepository.add_parcel(
            tracking_no=data["tracking_no"],
            receiver_phone=data["receiver_phone"],
            cabinet_number="A02",
            extra_info={"company": data["company"], "receiver_name": data["receiver_name"]}
        )

        return APIResponse(
            message=f"快捷操作完成：已入库 {data['tracking_no']}",
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
