import json
import random
from datetime import date, datetime
from zoneinfo import ZoneInfo
import numpy as np
from database.db_manager import DatabaseManager
from database.constants import (
    CABINET_PREFIXES,
    CABINET_NUM_MIN,
    CABINET_NUM_MAX,
    CABINET_MAX_CAPACITY
)

def _generate_cabinet_number(existing_numbers: set, allowed_cabinets: set | None = None) -> str:
    """从尚未占用的货柜号中随机选一个返回，若已满则抛出异常"""
    if allowed_cabinets is not None:
        available = sorted(set(allowed_cabinets) - set(existing_numbers))
        if not available:
            raise RuntimeError("可用机械臂货柜已满，无法分配新柜号")
        return random.choice(available)

    if len(existing_numbers) >= CABINET_MAX_CAPACITY:
        raise RuntimeError("所有货柜已满，无法分配新柜号")
    occupied = set(existing_numbers)
    while True:
        prefix = random.choice(CABINET_PREFIXES)
        num = random.randint(CABINET_NUM_MIN, CABINET_NUM_MAX)
        candidate = f"{prefix}{num:02d}"
        if candidate not in occupied:
            return candidate

class UserRepository:
    @staticmethod
    def add_user(phone: str, username: str, face_feature: np.ndarray, extra_info: dict = None) -> int:
        feature_bytes = face_feature.tobytes()
        extra_str = json.dumps(extra_info or {})
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (phone, username, face_feature, extra_info) 
                VALUES (?, ?, ?, ?)
            ''', (phone, username, feature_bytes, extra_str))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def get_user_by_id(cls, user_id: int) -> dict:
        with DatabaseManager.get_connection() as conn:
            import sqlite3
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, phone, username, is_active, extra_info, created_at, updated_at
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all_active_faces():
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, phone, username, face_feature FROM users WHERE is_active = 1')
            results = []
            for row in cursor.fetchall():
                results.append({
                    "user_id": row['user_id'],
                    "phone": row['phone'],
                    "username": row['username'],
                    "face_feature": np.frombuffer(row['face_feature'], dtype=np.float32)
                })
            return results

    @staticmethod
    def get_all_users(limit: int = 100, offset: int = 0):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, phone, username, is_active, extra_info, created_at 
                FROM users 
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            ''', (limit, offset))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "user_id": row['user_id'],
                    "phone": row['phone'],
                    "username": row['username'],
                    "is_active": row['is_active'],
                    "extra_info": json.loads(row['extra_info']) if row['extra_info'] else {},
                    "created_at": row['created_at']
                })
            return results

    @staticmethod
    def update_user(user_id: int, username: str = None, phone: str = None,
                    extra_info: dict = None, is_active: int = None) -> bool:
        """
        通用更新用户基本信息。
        所有参数除 user_id 外均可选，传入 None 表示不修改该字段。
        修改 phone 时需确保不与其他用户冲突（依赖数据库 UNIQUE 约束）。
        """
        set_parts = []
        params = []
        if username is not None:
            set_parts.append("username = ?")
            params.append(username)
        if phone is not None:
            set_parts.append("phone = ?")
            params.append(phone)
        if extra_info is not None:
            set_parts.append("extra_info = ?")
            params.append(json.dumps(extra_info))
        if is_active is not None:
            set_parts.append("is_active = ?")
            params.append(is_active)
        if not set_parts:
            return False
        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE users SET {', '.join(set_parts)} WHERE user_id = ?"
        params.append(user_id)
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def update_user_status(user_id: int, is_active: int) -> bool:
        """快捷方法：仅修改启用/禁用状态，内部复用 update_user"""
        return UserRepository.update_user(user_id=user_id, is_active=is_active)

    @staticmethod
    def hard_delete_user(user_id: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0


class ParcelRepository:
    @staticmethod
    def get_active_cabinet_numbers() -> set:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT cabinet_number FROM parcels WHERE status = 1')
            return {row['cabinet_number'] for row in cursor.fetchall()}

    @staticmethod
    def allocate_cabinet(allowed_cabinets: set | None = None) -> str:
        """只分配柜号，不写入包裹记录。用于先执行机械臂、成功后再入库。"""
        occupied = ParcelRepository.get_active_cabinet_numbers()
        return _generate_cabinet_number(occupied, allowed_cabinets)

    @staticmethod
    def get_parcel_by_tracking_no(tracking_no: str) -> dict:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parcels WHERE tracking_no = ?', (tracking_no,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def add_parcel(tracking_no: str, cabinet_number: str = "", receiver_phone: str = "",
                   target_location: str = "", status: int = 1, extra_info: dict = None) -> dict:
        """
        包裹入库。若 cabinet_number 为空则自动分配。
        返回新增包裹的完整信息字典（含 cabinet_number）。
        """
        target_location = target_location.upper()
        if target_location not in {"A", "B"}:
            raise ValueError("包裹目标类别必须是 A 或 B")
        extra_str = json.dumps(extra_info or {})
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            if not cabinet_number:
                cursor.execute('SELECT cabinet_number FROM parcels WHERE status = 1')
                occupied = {row['cabinet_number'] for row in cursor.fetchall()}
                cabinet_number = _generate_cabinet_number(occupied)
            pickup_code = cabinet_number
            cursor.execute('''
                INSERT INTO parcels (
                    tracking_no, pickup_code, cabinet_number, receiver_phone,
                    target_location, status, extra_info, in_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tracking_no, pickup_code, cabinet_number, receiver_phone,
                  target_location, status, extra_str, now_str))
            conn.commit()
            new_id = cursor.lastrowid
            # 查询完整信息返回
            cursor.execute('SELECT * FROM parcels WHERE parcel_id = ?', (new_id,))
            row = cursor.fetchone()
            return dict(row)

    @staticmethod
    def get_all_parcels_by_phone(phone: str):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, cabinet_number, receiver_phone, target_location,
                       status, in_time, out_time, extra_info
                FROM parcels 
                WHERE receiver_phone = ?
                ORDER BY in_time DESC
            ''', (phone,))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "parcel_id": row['parcel_id'],
                    "tracking_no": row['tracking_no'],
                    "cabinet_number": row['cabinet_number'],
                    "receiver_phone": row['receiver_phone'],
                    "target_location": row['target_location'],
                    "status": row['status'],
                    "in_time": row['in_time'],
                    "out_time": row['out_time'],
                    "extra_info": row['extra_info']
                })
            return results

    @staticmethod
    def get_active_parcels_by_phone(phone: str):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, cabinet_number, receiver_phone, target_location,
                       status, in_time, out_time, extra_info
                FROM parcels 
                WHERE receiver_phone = ? AND status = 1
            ''', (phone,))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "parcel_id": row['parcel_id'],
                    "tracking_no": row['tracking_no'],
                    "cabinet_number": row['cabinet_number'],
                    "receiver_phone": row['receiver_phone'],
                    "target_location": row['target_location'],
                    "status": row['status'],
                    "in_time": row['in_time'],
                    "out_time": row['out_time'],
                    "extra_info": row['extra_info']
                })
            return results

    @staticmethod
    def get_all_parcels(limit: int = 100, offset: int = 0):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, pickup_code, cabinet_number, receiver_phone,
                       target_location, status, in_time, out_time, extra_info
                FROM parcels 
                ORDER BY in_time DESC LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_parcel_status(parcel_id: int, new_status: int) -> bool:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == 2 else None
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            if new_status == 2:
                cursor.execute('UPDATE parcels SET status = ?, out_time = ? WHERE parcel_id = ? AND status = 1', 
                               (new_status, now_str, parcel_id))
            else:
                cursor.execute('UPDATE parcels SET status = ? WHERE parcel_id = ?', 
                               (new_status, parcel_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def complete_pickup_and_increment(parcel_id: int, now: datetime | None = None) -> dict | None:
        now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
        out_time = now.strftime("%Y-%m-%d %H:%M:%S")
        business_date = now.date().isoformat()
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT target_location FROM parcels WHERE parcel_id = ? AND status = 1",
                (parcel_id,),
            ).fetchone()
            if row is None:
                return None
            target_location = row["target_location"]
            column = "target_a_count" if target_location == "A" else "target_b_count"
            cursor.execute(
                "UPDATE parcels SET status = 2, out_time = ? WHERE parcel_id = ? AND status = 1",
                (out_time, parcel_id),
            )
            if cursor.rowcount != 1:
                return None
            cursor.execute('''
                INSERT INTO parcel_daily_counters (business_date)
                VALUES (?) ON CONFLICT(business_date) DO NOTHING
            ''', (business_date,))
            cursor.execute(f'''
                UPDATE parcel_daily_counters
                SET {column} = {column} + 1,
                    report_status = 'pending', published_at = NULL,
                    last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE business_date = ?
            ''', (business_date,))
            counts = cursor.execute('''
                SELECT target_a_count, target_b_count
                FROM parcel_daily_counters WHERE business_date = ?
            ''', (business_date,)).fetchone()
            conn.commit()
            return {
                "business_date": business_date,
                "target_location": target_location,
                "target_a_count": counts["target_a_count"],
                "target_b_count": counts["target_b_count"],
            }

    @staticmethod
    def delete_parcel(parcel_id: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM parcels WHERE parcel_id = ?', (parcel_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def get_parcel_by_id(parcel_id: int) -> dict:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parcels WHERE parcel_id = ?', (parcel_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def update_parcel(parcel_id: int, tracking_no: str = None, receiver_phone: str = None,
                      cabinet_number: str = None, status: int = None,
                      extra_info: dict = None, target_location: str = None) -> bool:
        set_parts = []
        params = []
        if tracking_no is not None:
            set_parts.append("tracking_no = ?")
            params.append(tracking_no)
        if receiver_phone is not None:
            set_parts.append("receiver_phone = ?")
            params.append(receiver_phone)
        if cabinet_number is not None:
            set_parts.append("cabinet_number = ?")
            params.append(cabinet_number)
        if target_location is not None:
            target_location = target_location.upper()
            if target_location not in {"A", "B"}:
                raise ValueError("包裹目标类别必须是 A 或 B")
            set_parts.append("target_location = ?")
            params.append(target_location)
        if status is not None:
            set_parts.append("status = ?")
            params.append(status)
            if status == 2:
                set_parts.append("out_time = ?")
                params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if extra_info is not None:
            set_parts.append("extra_info = ?")
            params.append(json.dumps(extra_info))
        if not set_parts:
            return False
        sql = f"UPDATE parcels SET {', '.join(set_parts)} WHERE parcel_id = ?"
        params.append(parcel_id)
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0


class AccessLogRepository:
    @staticmethod
    def add_log(user_id: int, action_type: str, snapshot_path: str = "",
                picked_parcels: list = None) -> int:
        parcels_str = json.dumps(picked_parcels or [])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO access_logs (user_id, action_type, snapshot_path, picked_parcels, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, action_type, snapshot_path, parcels_str, now_str))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_last_action(user_id: int, action_types: list[str] | None = None) -> str | None:
        query = 'SELECT action_type FROM access_logs WHERE user_id = ?'
        params = [user_id]
        if action_types:
            placeholders = ','.join(['?'] * len(action_types))
            query += f' AND action_type IN ({placeholders})'
            params.extend(action_types)
        query += ' ORDER BY log_id DESC LIMIT 1'
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row['action_type'] if row else None

    @staticmethod
    def get_recent_logs(limit: int = 50):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.log_id, l.action_type, l.timestamp, l.snapshot_path, l.picked_parcels, l.user_id,
                       u.username, u.phone 
                FROM access_logs l
                JOIN users u ON l.user_id = u.user_id
                ORDER BY l.timestamp DESC LIMIT ?
            ''', (limit,))
            results = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['picked_parcels'] = json.loads(row_dict['picked_parcels']) if row_dict['picked_parcels'] else []
                results.append(row_dict)
            return results
    @staticmethod
    def delete_logs_by_user_id(user_id: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM access_logs WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0

class ParcelDailyCounterRepository:
    @staticmethod
    def ensure_date(business_date: date | str) -> dict:
        value = business_date.isoformat() if isinstance(business_date, date) else business_date
        with DatabaseManager.get_connection() as conn:
            conn.execute('''
                INSERT INTO parcel_daily_counters (business_date)
                VALUES (?) ON CONFLICT(business_date) DO NOTHING
            ''', (value,))
            row = conn.execute(
                "SELECT * FROM parcel_daily_counters WHERE business_date = ?", (value,)
            ).fetchone()
            conn.commit()
            return dict(row)

    @staticmethod
    def get(business_date: date | str) -> dict | None:
        value = business_date.isoformat() if isinstance(business_date, date) else business_date
        with DatabaseManager.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM parcel_daily_counters WHERE business_date = ?", (value,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_before(before_date: date | str, pending_only: bool = False) -> list[dict]:
        value = before_date.isoformat() if isinstance(before_date, date) else before_date
        query = "SELECT * FROM parcel_daily_counters WHERE business_date < ?"
        if pending_only:
            query += " AND report_status != 'published'"
        query += " ORDER BY business_date"
        with DatabaseManager.get_connection() as conn:
            return [dict(row) for row in conn.execute(query, (value,)).fetchall()]

    @staticmethod
    def mark_publishing(business_date: str):
        with DatabaseManager.get_connection() as conn:
            conn.execute('''
                UPDATE parcel_daily_counters
                SET report_status = 'publishing', last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE business_date = ?
            ''', (business_date,))
            conn.commit()

    @staticmethod
    def mark_published(business_date: str):
        with DatabaseManager.get_connection() as conn:
            conn.execute('''
                UPDATE parcel_daily_counters
                SET report_status = 'published', published_at = CURRENT_TIMESTAMP,
                    last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE business_date = ?
            ''', (business_date,))
            conn.commit()

    @staticmethod
    def mark_failed(business_date: str, error: str):
        with DatabaseManager.get_connection() as conn:
            conn.execute('''
                UPDATE parcel_daily_counters
                SET report_status = 'pending', last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE business_date = ?
            ''', (error, business_date))
            conn.commit()
