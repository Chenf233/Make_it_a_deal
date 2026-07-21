import asyncio
import logging

from fastapi import APIRouter

from database.schemas import APIResponse
from services.motor import WHEEL_PINS, start_wheel, stop_all_wheels, stop_wheel

logger = logging.getLogger("SmartStation")
router = APIRouter(prefix="/wheels", tags=["Wheel Control"])


async def run_gpio_command(command, *args):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, command, *args)


@router.post("/stop-all", response_model=APIResponse)
async def stop_all():
    try:
        await run_gpio_command(stop_all_wheels)
        return APIResponse(message="四路轮子电机已全部停止")
    except Exception as exc:
        logger.exception("停止全部轮子电机失败")
        return APIResponse(code=500, message=f"停止全部轮子电机失败：{str(exc)}")


@router.post("/{pin}/start", response_model=APIResponse)
async def start(pin: int):
    if pin not in WHEEL_PINS:
        return APIResponse(code=400, message=f"不支持的轮子 GPIO 引脚：{pin}")

    try:
        await run_gpio_command(start_wheel, pin)
        return APIResponse(message=f"GPIO {pin} 已置为高电平")
    except Exception as exc:
        logger.exception("启动 GPIO %s 对应轮子电机失败", pin)
        return APIResponse(code=500, message=f"GPIO {pin} 启动失败：{str(exc)}")


@router.post("/{pin}/stop", response_model=APIResponse)
async def stop(pin: int):
    if pin not in WHEEL_PINS:
        return APIResponse(code=400, message=f"不支持的轮子 GPIO 引脚：{pin}")

    try:
        await run_gpio_command(stop_wheel, pin)
        return APIResponse(message=f"GPIO {pin} 已置为低电平")
    except Exception as exc:
        logger.exception("停止 GPIO %s 对应轮子电机失败", pin)
        return APIResponse(code=500, message=f"GPIO {pin} 停止失败：{str(exc)}")
