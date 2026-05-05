import serial
import time

# ===============配置串口参数==========================
# 'COMx' 在设备管理器中确认，波特率必须与 HAL 库中设置的一致
ser = serial.Serial('COM5', 115200, timeout=0.5)

def control_hardware(state):
    if state == "ON":
        ser.write(b'1')
        print("硬件已启动：闪灯 + 蜂鸣")
    else:
        ser.write(b'0')
        print("硬件已关闭")

try:
    while True:
        # 示例：获取用户输入来模拟“特定时间”的触发
        cmd = input("输入 1 开启，0 关闭 (输入 q 退出): ")
        if cmd == '1':
            control_hardware("ON")
        elif cmd == '0':
            control_hardware("OFF")
        elif cmd == 'q':
            break

except KeyboardInterrupt:
    pass
finally:
    ser.close()