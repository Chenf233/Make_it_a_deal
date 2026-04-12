import os
import sys

# 将项目根目录加入 sys.path (根据您的指令进行设置，确保能认到 database.xxx)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# 为了适应直接在 database 目录下运行，补充一层
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from database.db_manager import DatabaseManager
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.constants import DUMMY_USERS, DUMMY_PARCELS, DB_PATH

def run_test():
    print(f"[*] 数据库路径: {DB_PATH}")
    # 1. 初始化数据库结构
    DatabaseManager.init_db()
    print("[+] 数据库表结构初始化成功！")

    # 2. 插入测试用户 (带异常捕获，防止重复运行测试抛出 UNIQUE 约束错误)
    print("\n--- 正在录入用户 ---")
    for u in DUMMY_USERS:
        try:
            uid = UserRepository.add_user(u["phone"], u["username"], u["face_feature"], u["extra_info"])
            print(f"[+] 录入用户成功: {u['username']} (ID: {uid})")
        except Exception as e:
            print(f"[-] 录入用户 {u['username']} 失败 (可能已存在): {e}")

    # 3. 验证人脸特征读取与反序列化
    print("\n--- 系统启动：加载人脸特征到内存 ---")
    active_users = UserRepository.get_all_active_faces()
    for user in active_users:
        feature = user['face_feature']
        print(f"加载用户: {user['username']} | 特征维度: {feature.shape} | 类型: {feature.dtype}")
        assert feature.shape == (512,), "特征维度反序列化错误"

    # 4. 插入测试包裹
    print("\n--- 驿站入库：自动扫码录入 ---")
    for p in DUMMY_PARCELS:
        try:
            pid = ParcelRepository.add_parcel(p["tracking_no"], p["pickup_code"], p["receiver_phone"], p["status"], p["extra_info"])
            print(f"[+] 包裹入库成功: {p['pickup_code']} (单号: {p['tracking_no']})")
        except Exception as e:
            print(f"[-] 包裹 {p['pickup_code']} 入库失败 (可能已存在): {e}")

    # 5. 模拟核心业务逻辑：客户刷脸取件
    test_phone = "13800138000"
    print(f"\n--- 客户端业务：模拟用户({test_phone})刷脸进门 ---")
    
    # 5.1 查找该用户所有在库包裹
    my_parcels = ParcelRepository.get_active_parcels_by_phone(test_phone)
    pickup_codes = [p["pickup_code"] for p in my_parcels]
    print(f"[*] 查询到您的包裹，页面蜂鸣器及取件码高亮指令: {pickup_codes}")
    for p in my_parcels:
        print(f"    - 取件码: {p['pickup_code']}, 货架位置: {p['extra_info'].get('location', '未知')}")
    
    # 5.2 写入进门日志
    log_id = AccessLogRepository.add_log(user_id=1, action_type="IN", snapshot_path="/media/snapshots/1.jpg")
    print(f"[+] 写入进门日志成功, 记录 ID: {log_id}")

    print("\n" + "="*40)
    print("--- 模拟后台管理端 (Backend) 业务操作 ---")
    print("="*40)

    # 6. 后台拉取用户列表看板
    print("\n[+] 后台：拉取用户列表看板 (屏蔽了二进制特征，节省带宽)")
    all_users = UserRepository.get_all_users()
    for u in all_users:
        print(f"    - 用户 ID: {u['user_id']} | 姓名: {u['username']} | 手机号: {u['phone']} | 状态: {'正常' if u['is_active']==1 else '禁用'}")

    # 7. 用户出门，系统更新包裹状态与日志
    print("\n[+] 业务：用户出门，带走包裹 A001 和 B023")
    my_parcels = ParcelRepository.get_active_parcels_by_phone(test_phone)
    picked_codes =[]
    for p in my_parcels:
        # 业务逻辑：将状态从 1(在库) 更新为 2(已取走出库)
        success = ParcelRepository.update_parcel_status(p['parcel_id'], new_status=2)
        if success:
            picked_codes.append(p['pickup_code'])
    print(f"    - 成功将包裹 {picked_codes} 标记为出库(状态=2)并自动打上 out_time。")

    # 同时记录出门日志
    AccessLogRepository.add_log(user_id=1, action_type="OUT", snapshot_path="/media/snapshots/2_out.jpg", picked_parcels=picked_codes)
    print(f"    - 写入出门日志成功，带走物品快照：{picked_codes}")

    # 8. 后台审核进出监控日志
    print("\n[+] 后台：拉取进出门监控日志联表数据 (带人员姓名)")
    recent_logs = AccessLogRepository.get_recent_logs(limit=5)
    for log in recent_logs:
        print(f"    - [{log['timestamp']}] {log['username']}({log['phone']}) 执行动作: {log['action_type']} | 带走: {log['picked_parcels']} | 快照: {log['snapshot_path']}")

    # 9. 后台发现恶意用户，执行软禁用
    print("\n[+] 后台：管理员发现恶意用户 张三，执行账号封禁")
    # 假设张三的 user_id 为 1
    UserRepository.update_user_status(user_id=1, is_active=0)
    
    # 验证禁用结果：重启系统时将无法加载该用户特征
    active_faces_now = UserRepository.get_all_active_faces()
    active_names = [f["username"] for f in active_faces_now]
    print(f"    - 禁用操作后，系统重新加载的人脸池名单为: {active_names} (张三已被隔离)")

    print("\n[✓] 所有数据交互模块 (含管理端 CRUD) 业务逻辑测试闭环完成！")

if __name__ == "__main__":
    run_test()