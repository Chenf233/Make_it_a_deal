# 文件：constants.py

**职责**：集中管理数据库路径、货柜号生成规则及预置的离线测试数据。所有业务无关的魔法值均在此定义，方便全局修改。

**接口与常量**：
- `DB_PATH`: 数据库文件完整路径。
- `CABINET_PREFIXES`: 货柜号前缀列表，如 `["A","B","C","D"]`。
- `CABINET_NUM_MIN / CABINET_NUM_MAX`: 柜号数字范围（1~99）。
- `CABINET_MAX_CAPACITY`: 全库最大可用柜数。
- `DUMMY_USERS`: 两条测试用户（含512维随机人脸特征）。
- `DUMMY_PARCELS`: 三条测试包裹（`cabinet_number` 留空，入库时自动分配）。

**外部调用示例**：
```python
from database.constants import CABINET_MAX_CAPACITY, DUMMY_USERS
```