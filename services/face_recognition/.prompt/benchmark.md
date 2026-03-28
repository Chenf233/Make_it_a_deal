# 文件：benchmark.py
**职责**：独立运行的性能基准测试脚本 (Benchmark)。
通过显式实例化 CPU 和 GPU 两个 `FaceRecognizer` 对象，分别执行预热 (Warm-up) 后进行多轮连续的人脸特征提取压测。用于验证 CUDA 环境是否生效并计算出真实的单帧推理耗时与预估帧率 (FPS)。
**外部调用示例**：
```bash
# 在终端直接运行，观察 CPU 和 GPU 的性能差异
python services/face_recognition/test_face.py