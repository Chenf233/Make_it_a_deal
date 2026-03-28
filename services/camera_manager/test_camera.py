import sys
import os
import cv2

# 将项目根目录加入 sys.path，解决直接运行脚本时的模块导入报错问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.camera_manager import get_camera
from services.camera_manager.constants import CAMERA_TYPE

def test_camera():
    print(f"🚀 开始测试摄像头模块，当前配置模式: [{CAMERA_TYPE}]...")
    
    # 通过工厂函数，根据常量配置自动获取对应的摄像头实例
    cam = get_camera()
    
    # 1. 启动摄像头
    cam.start()
    print("✅ 摄像头已启动。将弹出预览窗口...")
    print("👉 提示：请在弹出的图像窗口上按 'q' 键退出预览。")
    
    try:
        while True:
            # 2. 持续获取视频帧
            success, frame = cam.get_frame()
            if success and frame is not None:
                # 使用 OpenCV 弹窗显示捕获的画面
                cv2.imshow(f"SmartStation Camera Test - {CAMERA_TYPE.upper()}", frame)
                
                # 等待 1 毫秒获取键盘输入，如果是 'q' 则打破循环退出
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n🛑 接收到退出指令 ('q')。")
                    break
            else:
                # 防止无画面时 CPU 死循环飙升，稍微休眠后继续尝试
                cv2.waitKey(100)
                
    except KeyboardInterrupt:
        print("\n🛑 被用户强行中断 (Ctrl+C)。")
        
    finally:
        # 3. 释放资源并销毁 OpenCV 窗口
        cam.stop()
        cv2.destroyAllWindows()
        print("🛑 测试结束，已释放摄像头资源并关闭所有窗口。")

if __name__ == "__main__":
    test_camera()