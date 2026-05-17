import os
import sys

# 将项目根目录加入 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from database.db_manager import DatabaseManager
from database.models import UserRepository, ParcelRepository, AccessLogRepository
from database.constants import DUMMY_USERS, DUMMY_PARCELS, DB_PATH, CABINET_PREFIXES, CABINET_NUM_MIN, CABINET_NUM_MAX

def simulate_frontend_requests():
    """
    模拟前端可能触发的所有请求行为：
    1. 数据库初始化
    2. 用户录入（预置数据）
    3. 包裹入库（自动分配货柜号）
    4. 客户刷脸进门 -> 查询在库包裹（获取货柜号作为取件码）
    5. 客户取走包裹 -> 更新状态
    6. 客户刷脸出门 -> 记录日志
    7. 后台查看包裹列表、日志
    8. 异常处理：重复入库、柜满测试
    """
    print("=" * 50)
    print("开始模拟前端请求流程（基于 constants 测试数据）")
    print("=" * 50)

    # 清理旧库（如需要可注释掉以保留数据）
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("[*] 已删除旧数据库，准备全新测试")

    # 1. 初始化表结构
    DatabaseManager.init_db()
    print("[+] 数据库表结构初始化完成")

    # 2. 录入用户（模拟后台管理端）
    print("\n--- 1. 后台录入用户 ---")
    for u in DUMMY_USERS:
        try:
            uid = UserRepository.add_user(
                phone=u["phone"],
                username=u["username"],
                face_feature=u["face_feature"],
                extra_info=u.get("extra_info")
            )
            print(f"   [+] 用户 {u['username']} 录入成功，user_id={uid}")
        except Exception as e:
            print(f"   [-] 用户 {u['username']} 录入失败: {e}")

    # 3. 包裹入库（模拟驿站工作端扫码）
    print("\n--- 2. 包裹入库（自动分配货柜号）---")
    assigned_cabinets = []
    for i, p in enumerate(DUMMY_PARCELS):
        try:
            pid = ParcelRepository.add_parcel(
                tracking_no=p["tracking_no"],
                cabinet_number="",  # 自动分配
                receiver_phone=p["receiver_phone"],
                status=p.get("status", 1),
                extra_info=p.get("extra_info")
            )
            # 获取刚插入的包裹信息，查看分配的柜号
            with DatabaseManager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT cabinet_number FROM parcels WHERE parcel_id = ?", (pid,))
                cab = cur.fetchone()["cabinet_number"]
            assigned_cabinets.append(cab)
            print(f"   [+] 包裹 {p['tracking_no']} 入库成功，货柜号={cab}, parcel_id={pid}")
        except Exception as e:
            print(f"   [-] 包裹 {p['tracking_no']} 入库失败: {e}")

    # 3.5 测试重复入库（应报错）
    print("\n--- 3. 重复入库异常测试 ---")
    try:
        ParcelRepository.add_parcel(
            tracking_no=DUMMY_PARCELS[0]["tracking_no"],
            receiver_phone=DUMMY_PARCELS[0]["receiver_phone"],
            extra_info={}
        )
        print("   [!] 未触发异常，请检查唯一约束")
    except Exception as e:
        print(f"   [!] 正确触发异常: {e}")

    # 4. 模拟客户刷脸进门（以张三为例）
    phone = "13800138000"
    print(f"\n--- 4. 客户刷脸进门 (phone={phone}) ---")
    active = ParcelRepository.get_active_parcels_by_phone(phone)
    if active:
        print(f"   [*] 用户 {phone} 当前在库包裹 {len(active)} 件：")
        for p in active:
            print(f"       - 取件码（货柜号）: {p['cabinet_number']}, 单号: {p['tracking_no']}")
    else:
        print("   [!] 无在库包裹")
    # 记录进门日志
    log1 = AccessLogRepository.add_log(
        user_id=1,  # 假设张三 user_id=1
        action_type="IN",
        snapshot_path="/media/snapshots/in_1.jpg"
    )
    print(f"   [+] 进门日志记录成功，log_id={log1}")

    # 5. 客户取走包裹（模拟取走所有在库包裹）
    print("\n--- 5. 客户取件 ---")
    picked = []
    for p in active:
        success = ParcelRepository.update_parcel_status(p['parcel_id'], 2)
        if success:
            picked.append(p['cabinet_number'])
            print(f"   [+] 包裹 {p['cabinet_number']} 状态已更新为'已取件'")
    print(f"   [*] 本次取走: {picked}")

    # 6. 客户刷脸出门
    print("\n--- 6. 客户刷脸出门 ---")
    # 出门前检查是否有漏拿（再次查询在库包裹）
    remaining = ParcelRepository.get_active_parcels_by_phone(phone)
    has_forgotten = len(remaining) > 0
    if has_forgotten:
        print(f"   [!] 警示：仍有 {len(remaining)} 件包裹未取走：{[r['cabinet_number'] for r in remaining]}")
    else:
        print("   [*] 所有包裹已取，可以离开")
    log2 = AccessLogRepository.add_log(
        user_id=1,
        action_type="OUT",
        snapshot_path="/media/snapshots/out_1.jpg",
        picked_parcels=picked
    )
    print(f"   [+] 出门日志记录成功，log_id={log2}")

    # 7. 后台管理端查看包裹列表及日志
    print("\n--- 7. 后台数据看板 ---")
    all_parcels = ParcelRepository.get_all_parcels()
    print("   包裹列表：")
    for p in all_parcels:
        status_text = {1:"在库",2:"已取件",3:"异常"}.get(p["status"],"未知")
        print(f"      单号:{p['tracking_no']} 柜号:{p['cabinet_number']} 状态:{status_text}")
    print("\n   进出日志：")
    logs = AccessLogRepository.get_recent_logs(limit=10)
    for l in logs:
        print(f"      用户:{l['username']} 动作:{l['action_type']} 时间:{l['timestamp']} 带走:{l['picked_parcels']}")

    # 8. 货柜满压力测试（可选：可自定义一个小的 CABINET_RANGE 来触发）
    print("\n--- 8. 货柜满分配异常测试（模拟大量入库）---")
    # 临时覆盖常量（仅测试用，此处直接操作)
    try:
        # 循环分配直到满
        for _ in range(500):
            # 生成新运单号避免冲突
            import uuid
            fake_tracking = str(uuid.uuid4())[:20]
            ParcelRepository.add_parcel(
                tracking_no=fake_tracking,
                cabinet_number="",
                receiver_phone="13800138000",
                status=1,
                extra_info={"test": True}
            )
    except RuntimeError as e:
        print(f"   [!] 达到柜满，异常捕获: {e}")
    except Exception as e:
        print(f"   [-] 其他异常: {e}")

    print("\n" + "=" * 50)
    print("前端请求模拟测试全部完成")
    print("=" * 50)

if __name__ == "__main__":
    simulate_frontend_requests()