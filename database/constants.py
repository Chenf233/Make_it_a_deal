import os
import numpy as np

# 数据库存储路径配置
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'smart_station.db')

# 确保 data 目录存在
os.makedirs(DB_DIR, exist_ok=True)

# ================= 模拟数据 (用于测试) =================

# 模拟 512 维的人脸特征向量 (float32)
DUMMY_FACE_FEATURE_1 = np.random.rand(512).astype(np.float32)
DUMMY_FACE_FEATURE_2 = np.random.rand(512).astype(np.float32)

DUMMY_USERS =[
    {
        "phone": "13800138000",
        "username": "张三",
        "face_feature": DUMMY_FACE_FEATURE_1,
        "is_active": 1,
        "extra_info": {"vip_level": "gold", "pref": "sms"}
    },
    {
        "phone": "13900139000",
        "username": "李四",
        "face_feature": DUMMY_FACE_FEATURE_2,
        "is_active": 1,
        "extra_info": {"vip_level": "normal"}
    }
]

DUMMY_PARCELS =[
    {
        "tracking_no": "JD123456789",
        "pickup_code": "A001",
        "receiver_phone": "13800138000",
        "status": 1, # 1=在库
        "extra_info": {"company": "京东", "location": "货架1-A", "weight": "2kg"}
    },
    {
        "tracking_no": "SF987654321",
        "pickup_code": "B023",
        "receiver_phone": "13800138000",
        "status": 1, 
        "extra_info": {"company": "顺丰", "location": "货架2-B"}
    },
    {
        "tracking_no": "ZT111222333",
        "pickup_code": "C105",
        "receiver_phone": "13900139000",
        "status": 1,
        "extra_info": {"company": "中通"}
    }
]