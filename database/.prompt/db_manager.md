# 文件：db_manager.py

**职责**：提供数据库连接管理与表结构初始化。使用上下文管理器自动开启 WAL 模式与外键约束，`init_db` 负责创建/升级表结构（当前版本 `parcels` 表已包含 `cabinet_number` 字段和对应索引）。

**接口**：
- `DatabaseManager.get_connection()`：返回上下文管理器，yield 一个 `sqlite3.Connection` 对象，其 `row_factory` 已被设置为 `sqlite3.Row`，支持列名访问。
- `DatabaseManager.init_db()`：创建 `users`、`parcels`（含 `cabinet_number`）、`access_logs` 三张核心表及相关索引。幂等操作，可重复执行。

**外部调用示例**：
```python
from database.db_manager import DatabaseManager
DatabaseManager.init_db()
```