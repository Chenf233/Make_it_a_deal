# 文件：backend_api.py

**职责**  
提供后台管理端所需的所有 HTTP API，包括用户注册、包裹看板、出入日志查询。  
所有接口统一返回 `APIResponse`，数据字段使用 `UserOut`、`ParcelOut`、`AccessLogOut` 等 Pydantic 模型。

**接口**

### 1. `POST /api/backend/users` – 注册新用户
- **输入**：`Form` 参数 `name` (姓名)、`phone` (手机号，需合法格式)，`UploadFile` `file` (人脸照片)。
- **处理流程**：
  1. 解码图片，调用 `app_state.face_recognizer.extract_feature` 提取人脸特征。
  2. 若未检测到人脸，返回 `400`。
  3. 调用 `UserRepository.add_user` 写入数据库，获取 `user_id`。
  4. 热更新内存特征缓存 `app_state.add_single_face_to_cache`（失败仅记日志）。
  5. 返回 `UserOut` 对象，`created_at` 为当前时间。
- **异常处理**：
  - 图片解码失败 → `400`
  - 人脸检测失败 → `400`
  - 数据库唯一约束冲突（手机号重复） → `409`
  - 其他数据库错误 → `500`（记录日志）
- **外部调用示例**：
```javascript
const form = new FormData();
form.append("name", "张三");
form.append("phone", "13800138000");
form.append("file", imageFile);
fetch("/api/backend/users", { method: "POST", body: form })
```

### 2. `GET /api/backend/parcels` – 包裹管理看板
- **输入**：`status`（可选，1/2/3 状态过滤）、`skip`、`limit` 分页参数。
- **处理流程**：
  1. 通过 `ParcelRepository.get_all_parcels` 获取全量包裹（数据库层暂未支持过滤与分页，路由层做内存过滤切片）。
  2. 构建 `phone → username` 映射，优先展示用户表中的真实收件人姓名。
  3. 组装 `ParcelOut` 列表（含 `cabinet_number` 作为取件码）。
- **外部调用示例**：
```javascript
fetch("/api/backend/parcels?status=1&skip=0&limit=20")
  .then(res => res.json())
  .then(data => console.log(data.data))
```

### 3. `GET /api/backend/logs` – 出入日志查询
- **输入**：`action_type`（可选，IN/OUT）、`skip`、`limit`。
- **处理流程**：调用 `AccessLogRepository.get_recent_logs` 获取近期日志（一次性拉取较多记录），路由层按动作过滤并切片，映射字段为 `AccessLogOut` 格式。
- **外部调用示例**：
```javascript
fetch("/api/backend/logs?action_type=IN&skip=0&limit=30")
```

### 4. `GET /api/backend/users` – 用户分页列表
- **输入**：`skip`（偏移量，>=0）、`limit`（每页条数，1~200）。
- **处理流程**：调用 `UserRepository.get_all_users` 获取分页数据，组装 `UserOut` 列表。
- **外部调用示例**：
```javascript
fetch("/api/backend/users?skip=0&limit=20")
  .then(res => res.json())
  .then(data => console.log(data.data))
```

### 5. `GET /api/backend/users/{user_id}` – 用户详情
- **输入**：路径参数 `user_id`。
- **处理流程**：调用 `UserRepository.get_user_by_id`，不存在时返回 `404`。
- **外部调用示例**：
```javascript
fetch("/api/backend/users/3")
  .then(res => res.json())
  .then(data => console.log(data.data))
```

### 6. `PUT /api/backend/users/{user_id}` – 更新用户信息
- **输入**：路径参数 `user_id`，JSON 体 `{ username?, phone?, extra_info? }`。
- **处理流程**：调用 `UserRepository.update_user`，传入非空字段；手机号冲突返回 `409`。
- **外部调用示例**：
```javascript
fetch("/api/backend/users/3", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ phone: "13900001111" })
})
```

### 7. `PUT /api/backend/users/{user_id}/status` – 启用/禁用用户
- **输入**：路径参数 `user_id`，JSON 体 `{ is_active: 0|1 }`。
- **处理流程**：调用 `UserRepository.update_user_status`，不存在返回 `404`。
- **外部调用示例**：
```javascript
fetch("/api/backend/users/3/status", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ is_active: 0 })
})
```

### 8. `DELETE /api/backend/users/{user_id}` – 删除用户
- **输入**：路径参数 `user_id`。
- **处理流程**：调用 `UserRepository.hard_delete_user`，捕获外键约束异常并返回 `500`。
- **外部调用示例**：
```javascript
fetch("/api/backend/users/3", { method: "DELETE" })

**TODO**
- 将包裹列表的状态过滤、分页逻辑下推到 `ParcelRepository` 的 SQL 层，避免全量加载。
- 日志接口同理，需增加 `AccessLogRepository.get_logs_filtered` 方法。
- 用户录入时增加图片存档功能。
- 抽象全局 `app_state` 依赖，改用 FastAPI 依赖注入。
- 当前 `UserOut` 未包含 `extra_info` 字段，管理端无法展示附加信息；待 `schemas.py` 中 `UserOut` 补充该字段后再行返回。
- 分页列表接口可扩展搜索（按姓名/手机号模糊匹配），需数据库层支持。
