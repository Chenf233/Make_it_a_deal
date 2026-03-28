# 文件：test_camera.py
**职责**：独立运行的可视化测试脚本。用于在不启动 FastAPI 服务的情况下，快速验证所选摄像头的加载逻辑，并弹窗实时渲染摄像头流（或虚拟图像）帧。
**接口**：
- `test_camera()`: 实例化选定摄像头，开启死循环捕获流并调用 `cv2.imshow` 渲染，按 `q` 退出并回收资源。
**外部调用示例**：
```bash
# 在终端中直接运行，会自动弹出可视化画面窗口
python services/camera_manager/test_camera.py