import asyncio
import logging
from typing import Literal

from fastapi import APIRouter

from database.models import StationCounterRepository
from database.schemas import APIResponse, StationCounterSet
from services.huawei_iot import huawei_iot
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


async def complete_destination_after(token: int, duration_seconds: float, destination: WheelDestination):
    await asyncio.sleep(duration_seconds)
    completed, status = await run_gpio_command(complete_destination, token)
    if completed:
        logger.info("轮子自动行驶完成，当前位置：%s", status["position"])
        try:
            counters, report_id = await huawei_iot.increment_and_report(destination.value)
            value = counters[f"counter_{destination.value}"]
            logger.info(
                "已记录到达 %s 地，累计值 %s，上报任务 %s",
                destination.value.upper(),
                value,
                report_id,
            )
        except Exception:
            logger.exception("记录或上报 %s 地到达事件失败", destination.value.upper())


def schedule_destination_completion(token: int, duration_seconds: float, destination: WheelDestination):
    task = asyncio.create_task(complete_destination_after(token, duration_seconds, destination))
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
            schedule_destination_completion(token, duration, destination)
            message = f"正在前往 {destination.value.upper()} 地，预计 {duration:.2f} 秒"
        else:
            message = f"当前已经位于 {destination.value.upper()} 地"
        return APIResponse(message=message, data=result["status"])
    except WheelBusyError as exc:
        return APIResponse(code=409, message=str(exc), data=await run_gpio_command(get_wheel_status))
    except Exception as exc:
        logger.exception("前往 %s 地失败", destination.value.upper())
        return APIResponse(code=500, message=f"自动行驶失败：{str(exc)}")


@router.get("/counters", response_model=APIResponse)
async def counters():
    return APIResponse(data=await run_gpio_command(StationCounterRepository.get_counters))


@router.put("/counters/{station}", response_model=APIResponse)
async def set_counter(station: Literal["a", "b"], payload: StationCounterSet):
    try:
        counters_state, report_id = await huawei_iot.set_and_report(station, payload.value)
        return APIResponse(
            message=f"{station.upper()} 地累计值已设置并排队上报",
            data={**counters_state, "report_id": report_id},
        )
    except Exception as exc:
        logger.exception("设置 %s 地累计值失败", station.upper())
        return APIResponse(code=500, message=f"设置累计值失败：{str(exc)}")


@router.get("/iot-status", response_model=APIResponse)
async def iot_status():
    return APIResponse(data=huawei_iot.get_status())
