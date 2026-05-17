import sqlite3
from contextlib import contextmanager
from database.constants import DB_PATH

class DatabaseManager:
    @staticmethod
    @contextmanager
    def get_connection():
        """提供上下文管理的数据库连接，自动开启 WAL 模式和外键约束"""
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA foreign_keys=ON;')
            yield conn
        finally:
            conn.close()

    @classmethod
    def init_db(cls):
        """初始化所有核心数据表（已含货柜号字段）"""
        with cls.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    username TEXT,
                    face_feature BLOB NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    extra_info TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. 物流包裹表（新增 cabinet_number 字段）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parcels (
                    parcel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_no TEXT UNIQUE NOT NULL,
                    pickup_code TEXT,
                    cabinet_number TEXT NOT NULL,
                    receiver_phone TEXT NOT NULL,
                    status INTEGER NOT NULL DEFAULT 0,
                    in_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    out_time DATETIME,
                    extra_info TEXT
                )
            ''')
            # 索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_receiver_phone ON parcels(receiver_phone);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pickup_code ON parcels(pickup_code);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cabinet_number ON parcels(cabinet_number);')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON parcels(status);')

            # 3. 进出日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    snapshot_path TEXT,
                    picked_parcels TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            conn.commit()