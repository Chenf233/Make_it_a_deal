# 文件：backend_api.py
**职责**：提供后台管理端接口，处理人员全生命周期管理（包含图片上传与特征热更新）、全局包裹数据检索与业务日志监控。
**接口**：
- `POST /backend/users`: 接收用户表单与图片，提取特征后写入数据库与系统内存缓存，返回 `APIResponse[UserOut]`。
- `GET /backend/parcels`: 分页按状态查询全局包裹列表，返回 `APIResponse[List[ParcelOut]]`。
- `GET /backend/logs`: 分页获取人员进出与业务操作关联日志，返回 `APIResponse[List[AccessLogOut]]`。
**外部调用示例**：
```javascript
// 前端上传新客户与人脸照片
const formData = new FormData();
formData.append("name", "李四");
formData.append("phone", "13800138000");
formData.append("file", fileInput.files[0]);

fetch("/backend/users", {
    method: "POST",
    body: formData
}).then(res => res.json());