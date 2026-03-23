#ver1 可实时推导

from ultralytics import YOLO
import cv2
import sys

def stream_inference(
    model_path: str,
    source: str | int,
    conf_threshold: float = 0.5,  # 置信度阈值（低于此值的检测结果不显示）
    save_video: bool = False,     # 是否保存推理后的视频
    save_path: str = "unnamed_output.mp4",# 保存视频路径
    show_window: bool = True      # 是否实时显示推理窗口
):
    """
    YOLO11 流数据推理核心函数
    :param model_path: 训练好的模型路径（如best.pt）
    :param source: 流数据源：
                   - 本地摄像头：0（默认摄像头）、1（外接摄像头）
                   - 本地视频："test.mp4"（视频文件路径）
                   - RTSP流："rtsp://admin:123456@192.168.1.100:554/stream"
    :param conf_threshold: 检测置信度阈值
    :param save_video: 是否保存推理结果视频
    :param save_path: 保存视频路径
    :param show_window: 是否显示实时推理窗口
    """
    # 1. 加载训练好的YOLOv11模型
    try:
        model = YOLO(model_path)
        print(f"✅ 成功加载模型: {model_path}")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        sys.exit(1)

    # 2. 打开流数据源
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ 无法打开流数据源: {source}")
        sys.exit(1)

    # 3. 配置视频保存（若需要）
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # 视频编码格式
    fps = int(cap.get(cv2.CAP_PROP_FPS))      # 流的帧率
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # 帧宽度
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))# 帧高度
    video_writer = None
    if save_video:
        video_writer = cv2.VideoWriter(save_path, fourcc, fps, (width, height))
        print(f"📹 推理结果将保存至: {save_path}")

    # 4. 逐帧推理主循环
    print(f"🚀 开始流推理（按 'q' 退出）...")
    while cap.isOpened():
        # 读取单帧
        ret, frame = cap.read()
        if not ret:
            print("⚠️ 流数据读取完毕/中断，退出推理")
            break

        # 模型推理（关键步骤）
        results = model(
            frame,
            conf=conf_threshold,  # 置信度阈值
            iou=0.45,             # NMS交并比阈值
            imgsz=640,            # 推理图片尺寸（和训练时一致）
            device=0              # 推理设备（0=GPU，cpu=CPU）
        )

        # 将推理结果绘制到帧上
        annotated_frame = results[0].plot()  # YOLO内置绘制函数

        # 保存帧（若开启）
        if save_video and video_writer:
            video_writer.write(annotated_frame)

        # 实时显示推理窗口
        if show_window:
            cv2.imshow("YOLOv11 Stream Inference", annotated_frame)
            
            # 按q键退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("🛑 用户手动退出推理")
                break

    # 5. 释放资源（关键，避免内存泄漏）
    cap.release()
    if save_video and video_writer:
        video_writer.release()
    cv2.destroyAllWindows()
    print("✅ 推理结束，资源已释放")

# -------------------------- 自定义配置（修改这里！）--------------------------
if __name__ == "__main__":
    # 配置参数（根据你的场景修改）
    MODEL_PATH = 'best.pt'  # 你的模型路径
    # 流数据源（三选一）：
    # SOURCE = 0  # 本地摄像头（默认）
    # SOURCE = "test_video.mp4"  # 本地视频文件
    SOURCE = 0 

    # 执行推理
    stream_inference(
        model_path=MODEL_PATH,
        source=SOURCE,
        conf_threshold=0.80,
        save_video=True,  # 是否保存推理视频
        save_path="ver1_output.mp4",
        show_window=True
    )

