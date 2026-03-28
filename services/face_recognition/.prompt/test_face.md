# 文件：test_face.py
**职责**：基于真实图片数据集的独立测试脚本。验证InsightFace加载状态，并读取 `pics` 目录下的四张图片（无人脸、人物A图1、人物A图2、人物B图1），测试提取逻辑与交叉相似度比对逻辑。
**外部调用示例**：
```bash
# 在终端运行，观察相似度得分和识别True/False结果
python services/face_recognition/test_face.py