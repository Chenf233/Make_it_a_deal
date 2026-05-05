# 文件：models.py
**职责**：核心数据访问层 (DAO/Repository)，禁止外部直接写 SQL。实现读写分离逻辑（如拉取全部用户时不拉取极占带宽的二进制人脸特征），并封装软删除与级联状态机的业务规则。
**接口**：
- **`UserRepository`**:
  - `add_user(phone: str, username: str, face_feature: np.ndarray, extra_info: dict = None)`: 新增用户并序列化人脸特征 (NumPy 变 BLOB)。
  - `get_all_active_faces() -> List[dict]`: **高频接口**。系统启动时调用，拉取所有可用人脸进入内存矩阵做 1:N 对比。
  - `get_user_by_id(user_id: int) -> Optional[dict]`: 【高频接口】根据主键获取用户基本信息字典（已自动剔除 BLOB 人脸特征避免内存溢出）。
  - `get_all_users(limit, offset)`: 【管理端】获取分页用户列表（剔除了 BLOB 特征）。
  - `update_user_status(user_id, is_active)`: 【管理端】软删除/启用用户。
  - `hard_delete_user(user_id)`: 【管理端】物理删除（需慎用）。
- **`ParcelRepository`**:
  - `add_parcel(tracking_no: str, pickup_code: str, receiver_phone: str, status: int = 1, extra_info: dict = None)`: 驿站端扫码入库。
  - `get_active_parcels_by_phone(phone)`: **高频接口**。客户刷脸后，查出所有状态为 1 (在库) 的包裹用于前端亮灯。
  - `get_all_parcels(limit, offset)`: 【管理端】包裹状态全量看板。
  - `update_parcel_status(parcel_id, status)`: 【业务/管理端】更新包裹状态（更新为 2 时会自动打上出库时间）。
  - `delete_parcel(parcel_id)`: 【管理端】删除错录包裹。
- **`AccessLogRepository`**:
  - `add_log(user_id, action_type, snapshot_path, picked_parcels)`: 记录进门(IN)出门(OUT)动作及拿走的包裹快照。
  - `get_recent_logs(limit)`: 【管理端】获取进出监控数据（已执行 JOIN 联表查询补齐了人名和手机号）。

**外部调用示例**：
```python
from database.models import ParcelRepository, AccessLogRepository

# 客户出门：状态标记为 2 (出库)
ParcelRepository.update_parcel_status(parcel_id=101, new_status=2)

# 写入出门快照监控
AccessLogRepository.add_log(
    user_id=1, 
    action_type="OUT", 
    snapshot_path="/media/out.jpg", 
    picked_parcels=["A001"]
)