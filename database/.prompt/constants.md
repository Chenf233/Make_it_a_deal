# 文件：constants.py
**职责**：集中管理数据库模块的物理存储路径，并在未对接真实硬件前，提供结构完善的 Mock 数据用于单元测试。
**接口**：
- `DB_PATH`: SQLite 数据库文件的绝对路径 (`database/data/smart_station.db`)。
- `DUMMY_USERS`: 包含假手机号、假人脸向量的列表。
- `DUMMY_PARCELS`: 模拟包裹结构。
**外部调用示例**：
```python
from database.constants import DB_PATH, DUMMY_USERS
print(f"当前数据库连接于: {DB_PATH}")