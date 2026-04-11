import qrcode
import json
import cv2
from pyzbar.pyzbar import decode
import sqlite3
import argparse
import sys
from datetime import datetime

#======================可改部分==============================
class Config:
    VIDEO_SOURCE = 0 
    QR_SAVE_NAME = "restart/ver1.png"
    DB_SAVE_NAME = "restart/ver1.db"
#===========================================================

# ==================== 核心功能 ====================

def generate_qr(parcel_data: dict, filename: str = "unnamed.png"):
    data_to_encode = {k: v for k, v in parcel_data.items() if k != "parcel_id"}
    json_str = json.dumps(data_to_encode, ensure_ascii=False, separators=(',', ':'))
    
    qr = qrcode.QRCode(version=4, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(json_str)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"✅ 二维码已保存至: {filename}")

def save_to_db(parcel_dict: dict, db_path: str = "unnamed.db"):
    """保存数据到数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parcel (
            parcel_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_no TEXT UNIQUE NOT NULL,
            company TEXT,
            receiver_name TEXT NOT NULL,
            receiver_phone TEXT NOT NULL,
            status INTEGER NOT NULL,
            location TEXT,
            in_time TEXT,
            out_time TEXT,
            remark TEXT
        )
    ''')
    try:
        cursor.execute('''
            INSERT INTO parcel (tracking_no, company, receiver_name, receiver_phone, status, location, in_time, out_time, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            parcel_dict.get('tracking_no'), parcel_dict.get('company'),
            parcel_dict.get('receiver_name'), parcel_dict.get('receiver_phone'),
            parcel_dict.get('status'), parcel_dict.get('location'),
            parcel_dict.get('in_time'), parcel_dict.get('out_time'), parcel_dict.get('remark')
        ))
        conn.commit()
        print(f"✅ 数据库入库成功: {parcel_dict.get('tracking_no')}")
        return True
    except sqlite3.IntegrityError:
        print(f"⚠️ 跳过：单号 {parcel_dict.get('tracking_no')} 已存在")
        return False
    finally:
        conn.close()

def scan_from_camera(db_path: str = "unnamed.db"):
    """通过摄像头实时识别"""
    cap = cv2.VideoCapture(Config.VIDEO_SOURCE)
    print("📷 摄像头已启动，对准二维码即可识别。按 'q' 键退出。")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 识别当前帧中的二维码
        decoded_objects = decode(frame)
        for obj in decoded_objects:
            # 提取数据
            qr_data = obj.data.decode('utf-8')
            try:
                data = json.loads(qr_data)
                if 'tracking_no' in data:
                    # 在屏幕上画框（可选）
                    (x, y, w, h) = obj.rect
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "SUCCESS", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 存入数据库
                    save_to_db(data, db_path)
                    
                    # 识别成功后停顿一下，防止重复录入
                    cv2.imshow('QR Scanner', frame)
                    cv2.waitKey(2000) 
            except Exception as e:
                pass

        cv2.imshow('QR Scanner', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# ==================== Main 函数 ====================

def main():
    parser = argparse.ArgumentParser(description="包裹二维码管理工具")
    parser.add_argument('--mode', choices=['generate', 'scan', 'camera'], help="执行模式")
    parser.add_argument('--data', type=str, help="生成模式的JSON数据")
    parser.add_argument('--image', type=str, help="图片识别模式的路径")
    parser.add_argument('--db', type=str, default='unnamed.db', help="数据库路径")
    
    args = parser.parse_args()

    # 1. 命令行模式
    if args.mode == 'generate' and args.data:
        generate_qr(json.loads(args.data))
    elif args.mode == 'camera':
        scan_from_camera(args.db)
    
    # 2. 交互模式（如果没有传参数）
    else:
        print("\n--- 包裹系统管理工具 ---")
        print("1. 生成示例二维码")
        print("2. 开启摄像头实时扫描")
        print("3. 退出")
        choice = input("请选择 (1/2/3): ")


#======================可改部分==============================
        if choice == '1':
            sample = {
                "tracking_no": f"SF{datetime.now().strftime('%m%d%H%M%S')}",  #用目前时间当作唯一快递单号，偷点懒
                "company": "顺丰速运",
                "receiver_name": "虞",
                "receiver_phone": "13800138000",
                "status": 1,
                "in_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
#===========================================================
            generate_qr(sample,Config.QR_SAVE_NAME)
        elif choice == '2':
            scan_from_camera(Config.DB_SAVE_NAME)
        else:
            sys.exit()

if __name__ == "__main__":
    main()