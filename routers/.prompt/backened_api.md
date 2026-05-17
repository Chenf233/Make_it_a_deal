# 文件：backend_api.py

**职责**  
提供后台管理端所需的所有 HTTP API，包括用户注册、包裹看板、出入日志查询。  
所有接口统一返回 `APIResponse`，数据字段使用 `UserOut`、`ParcelOut`、`AccessLogOut` 等 Pydantic 模型。

**接口**

### 1. `POST /backend/users` – 注册新用户
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
fetch("/backend/users", { method: "POST", body: form })
```

### 2. `GET /backend/parcels` – 包裹管理看板
- **输入**：`status`（可选，1/2/3 状态过滤）、`skip`、`limit` 分页参数。
- **处理流程**：
  1. 通过 `ParcelRepository.get_all_parcels` 获取全量包裹（数据库层暂未支持过滤与分页，路由层做内存过滤切片）。
  2. 构建 `phone → username` 映射，优先展示用户表中的真实收件人姓名。
  3. 组装 `ParcelOut` 列表（含 `cabinet_number` 作为取件码）。
- **外部调用示例**：
```javascript
fetch("/backend/parcels?status=1&skip=0&limit=20")
  .then(res => res.json())
  .then(data => console.log(data.data))
```

### 3. `GET /backend/logs` – 出入日志查询
- **输入**：`action_type`（可选，IN/OUT）、`skip`、`limit`。
- **处理流程**：调用 `AccessLogRepository.get_recent_logs` 获取近期日志（一次性拉取较多记录），路由层按动作过滤并切片，映射字段为 `AccessLogOut` 格式。
- **外部调用示例**：
```javascript
fetch("/backend/logs?action_type=IN&skip=0&limit=30")
```

**TODO**
- 将包裹列表的状态过滤、分页逻辑下推到 `ParcelRepository` 的 SQL 层，避免全量加载。
- 日志接口同理，需增加 `AccessLogRepository.get_logs_filtered` 方法。
- 用户录入时增加图片存档功能。
- 抽象全局 `app_state` 依赖，改用 FastAPI 依赖注入。
```