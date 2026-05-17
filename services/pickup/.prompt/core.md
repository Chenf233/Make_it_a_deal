# 文件：core.py
**职责**：实现 `PickupHandler` 类，协调摄像头帧捕获、QRScanner 解码、数据库包裹归属校验及状态更新。内部包含 `handle_pickup(user_id)` 方法，完成“抓帧→扫描→验证→更新状态→写日志”完整链路。  
**接口**：  
- `PickupHandler()`: 无参构造，无任何内部状态。  
- `async handle_pickup(user_id: int) -> Tuple[bool, str, Optional[Dict]]`:  
  - 参数: `user_id` 进门验证时获得的用户 ID。  
  - 返回: `(success, message, parcel_info_dict_or_None)`。若成功，`parcel_info` 包含 `parcel_id`, `tracking_no`, `cabinet_number`。  
**外部调用示例**：
```python
from services.pickup.core import PickupHandler
handler = PickupHandler()
ok, msg, data = await handler.handle_pickup(123)
if ok:
    print(f"确认取件: {data['tracking_no']}, 柜号 {data['cabinet_number']}")
```
**备注**：目前通过遍历用户所有在库包裹匹配 tracking_no，TODO 建议在 ParcelRepository 增加按单号查询方法以优化大数据量场景。取件成功后自动写入 `action_type='PICKUP'` 日志。
```