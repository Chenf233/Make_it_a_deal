import sys
import os
import cv2
import numpy as np

# 将项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.face_recognition.core import FaceRecognizer
from services.face_recognition.constants import (
    IMG_FACE_NAN, IMG_FACE_1_1, IMG_FACE_1_2, IMG_FACE_2_1
)

def test_face_recognition():
    print("🚀 正在加载 InsightFace 模型，请稍候... (首次运行可能会自动下载模型)")
    recognizer = FaceRecognizer()
    print("✅ 模型加载成功！\n")

    # 准备图片路径字典
    image_paths = {
        "faceNaN": IMG_FACE_NAN,
        "face1-1": IMG_FACE_1_1,
        "face1-2": IMG_FACE_1_2,
        "face2-1": IMG_FACE_2_1
    }

    features = {}

    print("👉 第一阶段：测试人脸检测与特征提取")
    for name, path in image_paths.items():
        img = cv2.imread(path)
        if img is None:
            print(f"⚠️  错误: 无法读取 {name}.jpg，请检查 pics 文件夹是否存在该文件！路径: {path}")
            features[name] = None
            continue
        
        emb = recognizer.extract_feature(img)
        if emb is not None:
            print(f"✅[{name}.jpg] 成功检测到人脸，提取特征维度: {emb.shape}")
            features[name] = emb
        else:
            # 对于 faceNaN.jpg，这里预期输出未检测到
            print(f"❌ [{name}.jpg] 未检测到人脸")
            features[name] = None

    print("\n👉 第二阶段：测试特征比对逻辑")
    
    # 测试 1: 同一人比对 (face1-1 vs face1-2)
    emb1_1 = features.get("face1-1")
    emb1_2 = features.get("face1-2")
    if emb1_1 is not None and emb1_2 is not None:
        sim = recognizer.compute_similarity(emb1_1, emb1_2)
        match = recognizer.is_match(emb1_1, emb1_2)
        print(f"▶️ [人物A vs 人物A] face1-1 与 face1-2")
        print(f"   相似度: {sim:.4f} | 是否同一人: {match}  (预期结果: True)")
    else:
        print("⚠️ 缺少 face1-1 或 face1-2 的特征，跳过同一人比对测试。")

    print("-" * 40)

    # 测试 2: 不同人比对 (face1-1 vs face2-1)
    emb2_1 = features.get("face2-1")
    if emb1_1 is not None and emb2_1 is not None:
        sim = recognizer.compute_similarity(emb1_1, emb2_1)
        match = recognizer.is_match(emb1_1, emb2_1)
        print(f"▶️ [人物A vs 人物B] face1-1 与 face2-1")
        print(f"   相似度: {sim:.4f} | 是否同一人: {match}  (预期结果: False)")
    else:
        print("⚠️ 缺少 face1-1 或 face2-1 的特征，跳过不同人比对测试。")

if __name__ == "__main__":
    test_face_recognition()