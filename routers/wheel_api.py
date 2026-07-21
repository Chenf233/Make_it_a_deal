import asyncio
import logging

from fastapi import APIRouter

from database.schemas import APIResponse
from services.motor import (
    WheelBusyError,
    WheelDestination,
    WheelMotion,
    complete_destination,
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


async def complete_destination_after(token: int, duration_seconds: float):
    await asyncio.sleep(duration_seconds)
    completed, status = await run_gpio_command(complete_destination, token)
    if completed:
        logger.info("轮子自动行驶完成，当前位置：%s", status["position"])


def schedule_destination_completion(token: int, duration_seconds: float):
    task = asyncio.create_task(complete_destination_after(token, duration_seconds))
    _automatic_tasks.add(task)
    task.add_done_callback(_automatic_tasks.discard)


@router.get("/status", response_model=APIResponse)
async def status():
    return APIResponse(data=await run_gpio_command(get_wheel_status))


@router.post("/stop-all", response_model=APIResponse)
async def stop_all():
    try:
        state = await run_gpio_command(stop_all_wheels)
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
        duration = result["duration_seconds"]
        if token is not None:
            schedule_destination_completion(token, duration)
            message = f"正在前往 {destination.value.upper()} 地，预计 {duration:.2f} 秒"
        else:
            message = f"当前已经位于 {destination.value.upper()} 地"
        return APIResponse(message=message, data=result["status"])
    except WheelBusyError as exc:
        return APIResponse(code=409, message=str(exc), data=await run_gpio_command(get_wheel_status))
    except Exception as exc:
        logger.exception("前往 %s 地失败", destination.value.upper())
        return APIResponse(code=500, message=f"自动行驶失败：{str(exc)}")
