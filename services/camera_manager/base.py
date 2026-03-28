from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class BaseCamera(ABC):
    """摄像头的抽象基类"""
    
    @abstractmethod
    def start(self) -> None:
        """初始化摄像头并启动视频流获取（例如启动后台线程）"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止视频流获取并释放资源"""
        pass

    @abstractmethod
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        获取最新的一帧
        :return: (是否成功读取, BGR格式的图像矩阵)
        """
        pass