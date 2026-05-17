# 文件：models.py

**职责**：核心数据访问层（DAO/Repository），彻底隔离 SQL 语句，负责用户、包裹、日志的完整生命周期管理。本版本新增通用用户更新方法，覆盖后台管理“增删查改”全套需求。

### 用户仓库 `UserRepository`

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_user` | `phone: str`, `username: str`, `face_feature: np.ndarray`, `extra_info: dict` | `int` (user_id) | 新增用户，人脸特征转 BLOB 存储。 |
| `get_user_by_id` | `user_id: int` | `dict | None` | 返回用户基本信息字典（不包含 BLOB 人脸特征），字段：`user_id`, `phone`, `username`, `is_active`, `extra_info`, `created_at`, `updated_at`。 |
| `get_all_active_faces` | 无 | `List[dict]` | 加载所有 `is_active=1` 的用户，返回字典包含 `user_id`, `phone`, `username`, `face_feature`（已反序列化为 `np.float32` 数组）。 |
| `get_all_users` | `limit: int=100, offset: int=0` | `List[dict]` | 管理端分页列表，不含人脸特征。 |
| **`update_user`** | `user_id: int`, `username: str=None`, `phone: str=None`, `extra_info: dict=None`, `is_active: int=None` | `bool` | **新增** 通用更新方法。传入 None 的字段保持不变；修改手机号时需注意 UNIQUE 约束。`extra_info` 为 dict 会自动序列化。 |
| `update_user_status` | `user_id: int, is_active: int` | `bool` | 软启用/禁用，成功返回 `True`。 |
| `hard_delete_user` | `user_id: int` | `bool` | 物理删除，若有日志外键依赖会失败。 |

### 包裹仓库 `ParcelRepository`（货柜号核心）

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_parcel` | `tracking_no: str`, `cabinet_number: str=""`, `receiver_phone: str`, `status: int=1`, `extra_info: dict` | `int` (parcel_id) | **关键变更**：若 `cabinet_number` 为空，则自动从未占用的柜号池中随机分配（格式`前缀+两位数字`，如`A03`）。`pickup_code` 自动设为分配的 `cabinet_number`。若柜满抛出 `RuntimeError`。 |
| `get_active_parcels_by_phone` | `phone: str` | `List[dict]` | 查询指定手机号的所有 `status=1` (在库) 包裹，返回字段含 `parcel_id`, `tracking_no`, `cabinet_number`, `extra_info`。**前端取件码即为 `cabinet_number`**。 |
| `get_all_parcels` | `limit: int=100, offset: int=0` | `List[dict]` | 管理端看板，返回所有包裹字段（含 `cabinet_number`）。 |
| `update_parcel_status` | `parcel_id: int, new_status: int` | `bool` | 更新包裹状态，若 `new_status=2`（已取件）则自动设置 `out_time`。 |
| `delete_parcel` | `parcel_id: int` | `bool` | 删除包裹。 |

### 日志仓库 `AccessLogRepository`

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_log` | `user_id: int, action_type: str, snapshot_path: str=""`, `picked_parcels: list=None` | `int` (log_id) | 记录 IN/OUT 动作及带走的包裹编号列表。 |
| `get_recent_logs` | `limit: int=50` | `List[dict]` | 联表查询进出日志，附带用户姓名和手机号。 |

**外部调用示例**：
```python
from database.models import ParcelRepository, UserRepository

# 包裹入库（自动分配柜号）
pid = ParcelRepository.add_parcel("JD0001", receiver_phone="13800138000")

# 刷脸后获取取件码列表
parcels = ParcelRepository.get_active_parcels_by_phone("13800138000")
for p in parcels:
    print(p["cabinet_number"])  # 取件码
```