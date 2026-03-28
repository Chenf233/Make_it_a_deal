from .base import BaseCamera
from .real_camera import RealCamera
from .dummy_camera import DummyCamera
from .constants import CAMERA_TYPE

def get_camera() -> BaseCamera:
    """
    工厂函数：根据 constants.py 中的 CAMERA_TYPE 自动实例化并返回对应的摄像头对象。
    """
    if CAMERA_TYPE == "real":
        return RealCamera()
    else:
        return DummyCamera()

__all__ =["BaseCamera", "RealCamera", "DummyCamera", "get_camera"]