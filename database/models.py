import json
import numpy as np
from database.db_manager import DatabaseManager

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

    @staticmethod
    def get_all_active_faces():
        """【业务端】启动时，加载所有 active=1 的人脸向量到内存"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, phone, username, face_feature FROM users WHERE is_active = 1')
            
            results =[]
            for row in cursor.fetchall():
                results.append({
                    "user_id": row['user_id'],
                    "phone": row['phone'],
                    "username": row['username'],
                    "face_feature": np.frombuffer(row['face_feature'], dtype=np.float32)
                })
            return results

    # ================= 管理端 (Backend) 接口 =================

    @staticmethod
    def get_all_users(limit: int = 100, offset: int = 0):
        """【管理端】分页获取所有用户信息（包含被禁用的），用于前端用户列表页"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            # 注意：管理端不需要拉取庞大的 face_feature 二进制数据，节约带宽
            cursor.execute('''
                SELECT user_id, phone, username, is_active, extra_info, created_at 
                FROM users 
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            results =[]
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
        """【管理端】软删除/禁用/恢复 用户"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?', 
                           (is_active, user_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def hard_delete_user(user_id: int) -> bool:
        """【管理端】危险操作：物理删除用户（需确保没有关联的外键日志）"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            # 开启外键约束时，如果有 log 依赖会导致报错，这是预期的保护机制
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0


class ParcelRepository:
    @staticmethod
    def add_parcel(tracking_no: str, pickup_code: str, receiver_phone: str, status: int = 1, extra_info: dict = None) -> int:
        extra_str = json.dumps(extra_info or {})
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO parcels (tracking_no, pickup_code, receiver_phone, status, extra_info) 
                VALUES (?, ?, ?, ?, ?)
            ''', (tracking_no, pickup_code, receiver_phone, status, extra_str))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_active_parcels_by_phone(phone: str):
        """【业务端】查询某用户当前在库的所有包裹"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, pickup_code, extra_info 
                FROM parcels 
                WHERE receiver_phone = ? AND status = 1
            ''', (phone,))
            
            results =[]
            for row in cursor.fetchall():
                results.append({
                    "parcel_id": row['parcel_id'],
                    "tracking_no": row['tracking_no'],
                    "pickup_code": row['pickup_code'],
                    "extra_info": json.loads(row['extra_info']) if row['extra_info'] else {}
                })
            return results

    # ================= 管理端 (Backend) 接口 =================

    @staticmethod
    def get_all_parcels(limit: int = 100, offset: int = 0):
        """【管理端】获取包裹数据看板列表"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT parcel_id, tracking_no, pickup_code, receiver_phone, status, in_time, out_time, extra_info 
                FROM parcels 
                ORDER BY in_time DESC LIMIT ? OFFSET ?
            ''', (limit, offset))
            return[dict(row) for row in cursor.fetchall()]

    @staticmethod
    def update_parcel_status(parcel_id: int, new_status: int) -> bool:
        """
        【业务/管理端】更新包裹状态（如客户取走包裹，状态变为 2）
        如果是出库动作 (status=2)，系统自动记录 out_time
        """
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            if new_status == 2:  # 2 表示已取走出库
                cursor.execute('UPDATE parcels SET status = ?, out_time = CURRENT_TIMESTAMP WHERE parcel_id = ?', (new_status, parcel_id))
            else:
                cursor.execute('UPDATE parcels SET status = ? WHERE parcel_id = ?', (new_status, parcel_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_parcel(parcel_id: int) -> bool:
        """【管理端】删除录入错误的包裹单"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM parcels WHERE parcel_id = ?', (parcel_id,))
            conn.commit()
            return cursor.rowcount > 0


class AccessLogRepository:
    @staticmethod
    def add_log(user_id: int, action_type: str, snapshot_path: str = "", picked_parcels: list = None) -> int:
        parcels_str = json.dumps(picked_parcels or[])
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO access_logs (user_id, action_type, snapshot_path, picked_parcels) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, action_type, snapshot_path, parcels_str))
            conn.commit()
            return cursor.lastrowid

    # ================= 管理端 (Backend) 接口 =================
    
    @staticmethod
    def get_recent_logs(limit: int = 50):
        """【管理端】获取进出人员监控面板的数据"""
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            # 联表查询：方便直接展示人名和手机号，而不是干巴巴的 user_id
            cursor.execute('''
                SELECT l.log_id, l.action_type, l.timestamp, l.snapshot_path, l.picked_parcels, 
                       u.username, u.phone 
                FROM access_logs l
                JOIN users u ON l.user_id = u.user_id
                ORDER BY l.timestamp DESC LIMIT ?
            ''', (limit,))
            
            results =[]
            for row in cursor.fetchall():
                row_dict = dict(row)
                row_dict['picked_parcels'] = json.loads(row_dict['picked_parcels']) if row_dict['picked_parcels'] else[]
                results.append(row_dict)
            return results