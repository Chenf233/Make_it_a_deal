import sqlite3
from contextlib import contextmanager
from database.constants import DB_PATH

class DatabaseManager:
    SCHEMA_VERSION = 2

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
        """初始化核心表，并执行部署所需的轻量 SQLite 迁移。"""
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
            
            parcel_table = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'parcels'"
            ).fetchone()
            if parcel_table:
                columns = {row[1] for row in cursor.execute("PRAGMA table_info(parcels)").fetchall()}
                if "target_location" not in columns:
                    # 历史包裹没有可靠目标类别，按业务要求删除后重建。
                    cursor.execute("DROP TABLE parcels")

            # 2. 物流包裹表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parcels (
                    parcel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_no TEXT UNIQUE NOT NULL,
                    pickup_code TEXT,
                    cabinet_number TEXT NOT NULL,
                    receiver_phone TEXT NOT NULL,
                    target_location TEXT NOT NULL CHECK (target_location IN ('A', 'B')),
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

            # 4. 每日取件分类计数
            cursor.execute('DROP TABLE IF EXISTS station_counters')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parcel_daily_counters (
                    business_date TEXT PRIMARY KEY,
                    target_a_count INTEGER NOT NULL DEFAULT 0 CHECK (target_a_count BETWEEN 0 AND 2147483647),
                    target_b_count INTEGER NOT NULL DEFAULT 0 CHECK (target_b_count BETWEEN 0 AND 2147483647),
                    report_status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (report_status IN ('pending', 'publishing', 'published')),
                    published_at DATETIME,
                    last_error TEXT,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute(f'PRAGMA user_version = {cls.SCHEMA_VERSION}')
            conn.commit()
