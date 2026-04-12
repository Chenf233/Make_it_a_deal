# 模块：database (SQLite + DAO)
**职责**：系统的数据持久化层。封装 SQLite 底层操作，强制开启 WAL 模式应对并发，并通过 DAO（数据访问对象）模式彻底隔离 SQL 语句，向外部业务层只暴露纯 Python 对象与方法。
**接口**：
- `db_manager.py`: 负责建库、建表及连接池上下文管理。
- `models.py`: 核心数据仓库（Repository），包含 User, Parcel, AccessLog 三大业务实体的全生命周期 CRUD 接口。
- `constants.py`: 数据库路径配置与离线 Mock 数据。
**外部调用示例**：
```python
from database.db_manager import DatabaseManager
from database.models import UserRepository, ParcelRepository

# 初始化数据库
DatabaseManager.init_db()
# 业务调用
parcels = ParcelRepository.get_active_parcels_by_phone("13800138000")