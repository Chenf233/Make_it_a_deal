import cv2
import numpy as np
import os
import sys
# 将项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.scanner.core import QRScanner

def run_test():
    print("🚀 开始测试 QRScanner (当前已开启 Demo Mock 模式)")
    scanner = QRScanner()

    # 模拟摄像头持续读取了 5 帧图像
    for i in range(5):
        print(f"\n[模拟获取第 {i+1} 帧图像...]")
        
        # 创建一个全黑的虚拟图像阵列 (高480, 宽640, 3通道BGR)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 调用核心扫码接口
        annotated_frame, results = scanner.scan(dummy_frame)

        if results:
            print(f"✅ 成功解码出 {len(results)} 个包裹信息:")
            for data in results:
                print(f"   📦 单号: {data.get('tracking_no')} | "
                      f"收件人: {data.get('receiver_name')} | "
                      f"时间: {data.get('in_time')}")
        else:
            print("❌ 未扫描到有效包裹")

    print("\n✅ 测试完毕！循环获取演示数据机制正常工作。")

if __name__ == "__main__":
    run_test()