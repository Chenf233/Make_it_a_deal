import os

# 模型名称
MODEL_NAME = "buffalo_l"

# 图像检测的默认输入尺寸 (必须是 32 的整数倍)
DET_SIZE = (640, 480)

# 人脸比对的余弦相似度阈值 (ArcFace 建议阈值一般在 0.45 - 0.5 之间)
SIMILARITY_THRESHOLD = 0.45

# ONNXRuntime 执行提供者配置 (优先使用 GPU)
PROVIDERS =['CUDAExecutionProvider', 'CPUExecutionProvider']

# 测试图片路径配置
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PICS_DIR = os.path.join(CURRENT_DIR, "pics")

IMG_FACE_NAN = os.path.join(PICS_DIR, "faceNaN.jpg")    # 无人脸
IMG_FACE_1_1 = os.path.join(PICS_DIR, "face1-1.jpg")    # 人物A
IMG_FACE_1_2 = os.path.join(PICS_DIR, "face1-2.jpg")    # 人物A (另一张)
IMG_FACE_2_1 = os.path.join(PICS_DIR, "face2-1.jpg")    # 人物B