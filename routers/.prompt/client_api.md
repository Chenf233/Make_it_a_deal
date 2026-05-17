# 文件：client_api.py
**职责**：客户体验端 API 路由。负责处理客户刷脸进门、出门、视频流推送以及包裹确取扫描请求。所有业务逻辑委托给 `services` 层，自身仅作参数校验、响应组装及硬件事件触发。  
**接口**：  
- `POST /api/client/access/entry`  
  客户进门刷脸验证。响应 `FaceAuthResult`，包含用户信息、在库包裹列表（取件码即 `cabinet_number`），并触发开门硬件信号。  
- `POST /api/client/access/exit`  
  客户出门刷脸验证。**不修改包裹状态**，仅查询当前在库包裹，如有则返回遗忘提醒并触发蜂鸣报警。  
- `POST /api/client/confirm_pickup?user_id=<int>`  
  站内扫描确认取件。由前端传入用户 ID，服务端抓帧并调用扫码器识别包裹，验证归属后更新包裹状态为“已取件”，记录 PICKUP 日志。  
- `GET /api/client/video_feed`  
  推送 MJPEG 实时视频流，用于前端显示摄像头画面。  

**外部调用示例（前端 Ajax）**：
```javascript
// 进门刷脸
const entry = await fetch('/api/client/access/entry', {method:'POST'});
const { data } = await entry.json();
// data.user.id 需要暂存，用于后续确取请求
const userId = data.user.id;

// 扫描取件
const pickupResp = await fetch(`/api/client/confirm_pickup?user_id=${userId}`, {method:'POST'});
const pickupResult = await pickupResp.json();

// 出门刷脸
const exitResp = await fetch('/api/client/access/exit', {method:'POST'});
```
**注意事项**：  
- 前端必须维护用户进出状态机，防止进门后立即触发刷脸出门。建议通过界面按钮激活对应操作，或设置动作冷却时间。  
- `entry` 返回的 `user.id` 需跨页面保留，以用于取件确认和出门请求。  
- 取件码在 `active_parcels` 数组中的 `cabinet_number` 字段，直接展示给客户。
```