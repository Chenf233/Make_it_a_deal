import os

# 摄像头类型选择配置: "real" 代表真实物理摄像头, "dummy" 代表虚拟模拟摄像头
CAMERA_TYPE = "dummy"

# 默认摄像头索引 (真实摄像头)
DEFAULT_CAMERA_ID = 0

# 默认分辨率
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480

# 默认帧率 (用于 DummyCamera 模拟延迟)
DEFAULT_FPS = 30

# 虚拟摄像头测试图像的路径配置
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_IMAGE_PATH = os.path.join(CURRENT_DIR, "pics", "a1.jpg")