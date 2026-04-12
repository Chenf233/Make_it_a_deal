# 文件：db_manager.py
**职责**：管理底层的 SQLite 连接。采用 `@contextmanager` 确保每次 DB 操作后正确释放连接，内部强制开启了 `PRAGMA journal_mode=WAL` (解决读写锁冲突) 和 `PRAGMA foreign_keys=ON`。
**接口**：
- `DatabaseManager.get_connection()`: 上下文管理器，`yield` 一个配置好的 `sqlite3.Connection`。
- `DatabaseManager.init_db()`: 幂等操作，负责初始化系统的 3 张核心数据表及索引。
**外部调用示例**：
```python
from database.db_manager import DatabaseManager

# 在系统启动 (main.py) 时调用一次
DatabaseManager.init_db()

# 自定义 SQL 操作 (非必要不推荐，请优先使用 models.py)
with DatabaseManager.get_connection() as conn:
    cursor = conn.cursor()
    # do something...