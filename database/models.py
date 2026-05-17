import json
import random
import numpy as np
from database.db_manager import DatabaseManager
from database.constants import (
    CABINET_PREFIXES,
    CABINET_NUM_MIN,
    CABINET_NUM_MAX,
    CABINET_MAX_CAPACITY
)

def _generate_cabinet_number(existing_numbers: set) -> str:
    """从尚未占用的货柜号中随机选一个返回，若已满则抛出异常"""
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
    def update_user_status(user_id: int, is_active: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?', 
                           (is_active, user_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def hard_delete_user(user_id: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0


class ParcelRepository:
    @staticmethod
    def add_parcel(tracking_no: str, cabinet_number: str = "", receiver_phone: str = "",
                   status: int = 1, extra_info: dict = None) -> int:
        """
        包裹入库。若 cabinet_number 为空，则自动分配未占用的货柜号。
        pickup_code 自动设为与 cabinet_number 相同，方便前端取件码展示。
        """
        extra_str = json.dumps(extra_info or {})
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            if not cabinet_number:
                # 自动分配柜号：查询当前所有在库包裹的 cabinet_number
                cursor.execute('SELECT cabinet_number FROM parcels WHERE status = 1')
                occupied = {row['cabinet_number'] for row in cursor.fetchall()}
                cabinet_number = _generate_cabinet_number(occupied)
            pickup_code = cabinet_number  # 取件码即为货柜号
            cursor.execute('''
                INSERT INTO parcels (tracking_no, pickup_code, cabinet_number, receiver_phone, status, extra_info) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (tracking_no, pickup_code, cabinet_number, receiver_phone, status, extra_str))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_active_parcels_by_phone(phone: str):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, cabinet_number, extra_info
                FROM parcels 
                WHERE receiver_phone = ? AND status = 1
            ''', (phone,))
            results = []
            for row in cursor.fetchall():
                results.append({
                    "parcel_id": row['parcel_id'],
                    "tracking_no": row['tracking_no'],
                    "cabinet_number": row['cabinet_number'],
                    "extra_info": json.loads(row['extra_info']) if row['extra_info'] else {}
                })
            return results

    @staticmethod
    def get_all_parcels(limit: int = 100, offset: int = 0):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, pickup_code, cabinet_number, receiver_phone, status, in_time, out_time, extra_info 
                FROM parcels 
                ORDER BY in_time DESC LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_parcel_status(parcel_id: int, new_status: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            if new_status == 2:
                cursor.execute('UPDATE parcels SET status = ?, out_time = CURRENT_TIMESTAMP WHERE parcel_id = ?', 
                               (new_status, parcel_id))
            else:
                cursor.execute('UPDATE parcels SET status = ? WHERE parcel_id = ?', 
                               (new_status, parcel_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_parcel(parcel_id: int) -> bool:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM parcels WHERE parcel_id = ?', (parcel_id,))
            conn.commit()
            return cursor.rowcount > 0


class AccessLogRepository:
    @staticmethod
    def add_log(user_id: int, action_type: str, snapshot_path: str = "",
                picked_parcels: list = None) -> int:
        parcels_str = json.dumps(picked_parcels or [])
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO access_logs (user_id, action_type, snapshot_path, picked_parcels) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, action_type, snapshot_path, parcels_str))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_recent_logs(limit: int = 50):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT l.log_id, l.action_type, l.timestamp, l.snapshot_path, l.picked_parcels, 
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