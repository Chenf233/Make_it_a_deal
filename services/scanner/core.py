import cv2
import json
import numpy as np
from typing import Tuple, List
from pyzbar.pyzbar import decode

from services.scanner.constants import (
    BBOX_COLOR, BBOX_THICKNESS, 
    TEXT_COLOR, TEXT_SCALE, TEXT_THICKNESS,
    DEMO_MODE_ENABLED, DEMO_DATA_LIST
)

class QRScanner:
    """
    二维码/条码扫描器
    无状态类，只负责纯粹的图像处理和解码提取
    """
    def __init__(self):
        # 维护演示模式的下标，用于循环提取 DEMO 数据
        self._demo_index = 0
        
    def scan(self, frame: np.ndarray) -> Tuple[np.ndarray, List[dict]]:
        """
        扫描帧中的二维码并绘制边框
        :param frame: 原始图像(OpenCV BGR 格式)
        :return: (处理后画框的图像, 提取到的合法字典数据列表)
        """
        annotated_frame = frame.copy()
        
        # ================== 演示模式分支 ==================
        if DEMO_MODE_ENABLED:
            # 1. 获取当前的 Mock 数据
            mock_data = DEMO_DATA_LIST[self._demo_index]
            
            # 2. 更新下标（到底部后循环回首个）
            self._demo_index = (self._demo_index + 1) % len(DEMO_DATA_LIST)
            
            # 3. 模拟 UI 反馈，在画面正中央画一个虚拟的识别框
            h, w = annotated_frame.shape[:2]
            box_w, box_h = 200, 200
            x, y = (w - box_w) // 2, (h - box_h) // 2
            
            cv2.rectangle(annotated_frame, (x, y), (x + box_w, y + box_h), BBOX_COLOR, BBOX_THICKNESS)
            cv2.putText(annotated_frame, "DEMO DECODED", (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, TEXT_SCALE, TEXT_COLOR, TEXT_THICKNESS)
            
            # 返回加了框的图像和 Mock 数据列表
            return annotated_frame, [mock_data]

        decoded_objects = decode(frame)
        
        results =[]
        
        for obj in decoded_objects:
            try:
                # 尝试以 UTF-8 解码数据
                qr_text = obj.data.decode('utf-8')
                
                # 尝试解析为 JSON（业务强相关）
                data = json.loads(qr_text)
                
                # 校验是否为预期的快递包裹数据
                if 'tracking_no' in data:
                    results.append(data)
                    
                    # 绘制矩形框
                    (x, y, w, h) = obj.rect
                    cv2.rectangle(
                        annotated_frame, 
                        (x, y), (x + w, y + h), 
                        BBOX_COLOR, 
                        BBOX_THICKNESS
                    )
                    
                    # 绘制成功提示文字
                    cv2.putText(
                        annotated_frame, 
                        "DECODED", 
                        (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        TEXT_SCALE, 
                        TEXT_COLOR, 
                        TEXT_THICKNESS
                    )
            except (UnicodeDecodeError, json.JSONDecodeError):
                # 扫到非预期格式的二维码，直接忽略
                continue
            except Exception as e:
                # 留作后续日志系统的异常捕获点
                print(f"Decode Error: {e}")
                continue
                
        return annotated_frame, results