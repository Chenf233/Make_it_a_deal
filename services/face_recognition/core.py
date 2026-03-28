import numpy as np
import cv2
from typing import Optional, List
from insightface.app import FaceAnalysis
from numpy.linalg import norm

from .constants import MODEL_NAME, DET_SIZE, SIMILARITY_THRESHOLD, PROVIDERS

class FaceRecognizer:
    """
    人脸识别核心引擎
    负责加载 InsightFace 模型，进行人脸检测、特征提取及比对。
    """
    def __init__(self, providers: Optional[List[str]] = None):
        # 允许外部注入执行器，如果不传则使用 constants 中的默认配置
        active_providers = providers if providers is not None else PROVIDERS
        
        # 初始化 InsightFace 分析引擎
        self.app = FaceAnalysis(name=MODEL_NAME, providers=active_providers)
        
        # ctx_id=0 表示使用第一块 GPU (即使 fallback 到 CPU 也不影响)
        self.app.prepare(ctx_id=0, det_size=DET_SIZE)

    def extract_feature(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        从图像中提取最大人脸的特征向量
        :param frame: BGR 格式的图像 (OpenCV 默认格式)
        :return: 512 维的 float32 特征向量，若未检测到人脸则返回 None
        """
        faces = self.app.get(frame)
        if not faces:
            return None
        
        # 如果画面中有过多个人脸，为了驿站场景（单人刷脸），我们取 bounding box 面积最大的那个人脸
        if len(faces) > 1:
            faces = sorted(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)
            
        # 返回最大人脸的 embedding
        return faces[0].embedding

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        计算两个特征向量的余弦相似度
        """
        sim = np.dot(emb1, emb2) / (norm(emb1) * norm(emb2))
        return float(sim)

    def is_match(self, emb1: np.ndarray, emb2: np.ndarray, threshold: float = SIMILARITY_THRESHOLD) -> bool:
        """
        判断两个特征向量是否属于同一个人
        """
        sim = self.compute_similarity(emb1, emb2)
        return sim >= threshold