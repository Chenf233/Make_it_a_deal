import asyncio
import logging
from fastapi import APIRouter

from database.schemas import APIResponse
from services.huawei_iot import huawei_iot
from services.motor import (
    WheelBusyError,
    WheelDestination,
    WheelMotion,
    WheelPhase,
    advance_automatic_phase,
    confirm_logistics_center,
    get_wheel_status,
    start_destination,
    start_manual_motion,
    stop_all_wheels,
    stop_manual_motion,
)

logger = logging.getLogger("SmartStation")
router = APIRouter(prefix="/wheels", tags=["Wheel Control"])
_automatic_tasks = set()


async def run_gpio_command(command, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, command, *args)


async def run_automatic_cycle(token: int, phase_duration_seconds: float):
    for phase in (WheelPhase.OUTBOUND, WheelPhase.DWELL, WheelPhase.RETURNING):
        await asyncio.sleep(phase_duration_seconds)
        advanced, status = await run_gpio_command(
            advance_automatic_phase, token, phase.value
        )
        if not advanced:
            return
    logger.info("轮子自动循环完成，当前位置：%s", status["location"])


def schedule_automatic_cycle(token: int, phase_duration_seconds: float):
    task = asyncio.create_task(run_automatic_cycle(token, phase_duration_seconds))
    _automatic_tasks.add(task)
    task.add_done_callback(_automatic_tasks.discard)


async def cancel_automatic_tasks():
    tasks = list(_automatic_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@router.get("/status", response_model=APIResponse)
async def status():
    return APIResponse(data=await run_gpio_command(get_wheel_status))


@router.post("/stop-all", response_model=APIResponse)
async def stop_all():
    try:
        state = await run_gpio_command(stop_all_wheels)
        await cancel_automatic_tasks()
        return APIResponse(message="底盘已停止", data=state)
    except Exception as exc:
        logger.exception("停止底盘失败")
        return APIResponse(code=500, message=f"停止底盘失败：{str(exc)}")


@router.post("/motions/{motion}/start", response_model=APIResponse)
async def start_motion(motion: WheelMotion):
    try:
        state = await run_gpio_command(start_manual_motion, motion.value)
        return APIResponse(message=f"开始手动动作：{motion.value}", data=state)
    except WheelBusyError as exc:
        return APIResponse(code=409, message=str(exc), data=await run_gpio_command(get_wheel_status))
    except Exception as exc:
        logger.exception("启动底盘手动动作失败：%s", motion.value)
        return APIResponse(code=500, message=f"启动失败：{str(exc)}")


@router.post("/motions/{motion}/stop", response_model=APIResponse)
async def stop_motion(motion: WheelMotion):
    try:
        stopped, state = await run_gpio_command(stop_manual_motion, motion.value)
        message = f"手动动作已停止：{motion.value}" if stopped else "当前动作已结束，无需重复停止"
        return APIResponse(message=message, data=state)
    except Exception as exc:
        logger.exception("停止底盘手动动作失败：%s", motion.value)
        return APIResponse(code=500, message=f"停止失败：{str(exc)}")


@router.post("/destinations/{destination}", response_model=APIResponse)
async def go_to_destination(destination: WheelDestination):
    try:
        result = await run_gpio_command(start_destination, destination.value)
        token = result["token"]
        phase_duration = result["phase_duration_seconds"]
        schedule_automatic_cycle(token, phase_duration)
        name = "一号驿站" if destination == WheelDestination.A else "二号驿站"
        message = f"已启动{name}往返任务"
        return APIResponse(message=message, data=result["status"])
    except WheelBusyError as exc:
        return APIResponse(code=409, message=str(exc), data=await run_gpio_command(get_wheel_status))
    except Exception as exc:
        logger.exception("前往 %s 地失败", destination.value.upper())
        return APIResponse(code=500, message=f"自动行驶失败：{str(exc)}")


@router.post("/confirm-logistics-center", response_model=APIResponse)
async def confirm_center():
    try:
        state = await run_gpio_command(confirm_logistics_center)
        return APIResponse(message="已确认底盘位于物流中心", data=state)
    except WheelBusyError as exc:
        return APIResponse(code=409, message=str(exc), data=await run_gpio_command(get_wheel_status))
    except Exception as exc:
        logger.exception("确认物流中心位置失败")
        return APIResponse(code=500, message=f"确认失败：{str(exc)}")


@router.get("/iot-status", response_model=APIResponse)
async def iot_status():
    return APIResponse(data=huawei_iot.get_status())
