# 模块：database (SQLite + DAO)

**职责**：系统的数据持久化层。封装 SQLite 底层操作，强制开启 WAL 模式应对并发，并通过 DAO 模式隔离 SQL 语句。本模块已升级支持**货柜号自动分配**：入库时自动生成唯一货柜号，并将其作为取件码返回前端。

**接口**：
- `db_manager.py`: 建库、建表（含新增 `cabinet_number` 字段）及连接上下文管理。
- `models.py`: 核心数据仓库，负责用户、包裹（含货柜号分配逻辑）、日志的全生命周期操作。
- `constants.py`: 数据库路径配置、货柜号范围常量、离线测试数据。
- `schemas.py`: Pydantic 模型，定义 API 输入校验与统一响应结构（已同步 `cabinet_number` 字段）。
- `test_db.py`: 模拟所有前端业务行为的集成测试脚本。

**外部调用示例**：
```python
from database.db_manager import DatabaseManager
from database.models import ParcelRepository

DatabaseManager.init_db()
# 入库时无需指定柜号，系统自动分配
parcel_id = ParcelRepository.add_parcel(
    tracking_no="SF123456",
    receiver_phone="13800138000",
    extra_info={"company": "顺丰"}
)
```