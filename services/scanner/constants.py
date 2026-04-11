# 绘制 Bounding Box 的颜色 (B, G, R)
BBOX_COLOR = (0, 255, 0)
BBOX_THICKNESS = 2

# 文字配置
TEXT_COLOR = (0, 255, 0)
TEXT_SCALE = 0.5
TEXT_THICKNESS = 2

# 生成二维码默认配置
DEFAULT_QR_VERSION = 4
DEFAULT_BOX_SIZE = 10
DEFAULT_BORDER = 4

# 默认生成路径
DEFAULT_SAVE_PATH = "sample_qr.png"

# ==================== 演示模式配置 ====================
# 是否开启演示模式。为 True 时跳过真实解码，直接返回模拟数据和居中画框
DEMO_MODE_ENABLED = True 

# 预设的演示数据集 (固定随机数据，剥离了动态的 datetime 函数)
DEMO_DATA_LIST =[
    {
        "tracking_no": "SF0412120801",
        "company": "顺丰速运",
        "receiver_name": "虞大",
        "receiver_phone": "13800138001",
        "status": 1,
        "in_time": "2026-04-12 10:00:00"
    },
    {
        "tracking_no": "JD0412120802",
        "company": "京东物流",
        "receiver_name": "虞二",
        "receiver_phone": "13800138002",
        "status": 1,
        "in_time": "2026-04-12 11:30:00"
    },
    {
        "tracking_no": "YT0412120803",
        "company": "圆通速递",
        "receiver_name": "虞三",
        "receiver_phone": "13800138003",
        "status": 1,
        "in_time": "2026-04-12 14:15:00"
    }
]