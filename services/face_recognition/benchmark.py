import sys
import os
import cv2
import time
import numpy as np

# 将项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.face_recognition.core import FaceRecognizer
from services.face_recognition.constants import IMG_FACE_1_1

def benchmark(recognizer: FaceRecognizer, device_name: str, img: np.ndarray, iterations: int = 50):
    print(f"\n[{device_name}] 正在进行预热 (Warm-up)...")
    # 预热执行 3 次，触发 cuDNN 的 autotuning 和缓存机制，不计入测试时间
    for _ in range(3):
        recognizer.extract_feature(img)
    
    print(f"[{device_name}] 预热完毕，开始 {iterations} 次连续特征提取性能压测...")
    start_time = time.perf_counter()
    
    for _ in range(iterations):
        recognizer.extract_feature(img)
        
    end_time = time.perf_counter()
    total_time = end_time - start_time
    avg_time_ms = (total_time / iterations) * 1000
    fps = iterations / total_time
    
    print(f"✅ {device_name} 测试结果:")
    print(f"   - 总耗时: {total_time:.4f} 秒")
    print(f"   - 单帧平均耗时: {avg_time_ms:.2f} 毫秒")
    print(f"   - 预估帧率: {fps:.2f} FPS")
    return fps

def test_performance():
    print("🚀 正在加载测试图像...")
    img = cv2.imread(IMG_FACE_1_1)
    if img is None:
        print(f"❌ 无法读取 {IMG_FACE_1_1}，请检查图片是否存在！")
        return

    # === 1. 测试纯 CPU 性能 ===
    print("\n" + "="*40)
    print(" 🛠 初始化纯 CPU 推理引擎...")
    print("="*40)
    cpu_recognizer = FaceRecognizer(providers=['CPUExecutionProvider'])
    cpu_fps = benchmark(cpu_recognizer, "CPU (纯算力)", img, iterations=20)

    # === 2. 测试 GPU 性能 ===
    print("\n" + "="*40)
    print(" 🛠 初始化 GPU (CUDA) 推理引擎...")
    print("="*40)
    gpu_recognizer = FaceRecognizer(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    gpu_fps = benchmark(gpu_recognizer, "GPU (RTX 5070 Ti)", img, iterations=100)
    
    # === 3. 性能提升总结 ===
    ratio = gpu_fps / cpu_fps if cpu_fps > 0 else 0
    print("\n" + "🌟 "*10)
    print(f" 性能总结：GPU 加速比约为 {ratio:.1f} 倍！")
    print("🌟 "*10 + "\n")

if __name__ == "__main__":
    test_performance()