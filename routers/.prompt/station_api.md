# 文件：station_api.py
**职责**：驿站工作端 API 路由。负责快递员包裹入库扫码、实时监控视频流。核心逻辑委托给 scanner 服务与数据库层，自身仅做校验与响应组装。
**接口**：
- `POST /station/scan_in`：
  触发摄像头抓帧，通过 QRScanner 解码包裹信息，校验关键字段后调用 ParcelRepository.add_parcel 完成入库。
  系统自动分配货柜号，取件码即柜号（cabinet_number）。
  返回 `ScanResultData`，包含单号、公司、收件人、手机号、货柜号、是否新用户。
- `GET /station/video_feed`：
  推送 MJPEG 实时视频流，供驿站端监控货物区（与人脸共用摄像头，前端应确保入库扫描时获取画面优先）。

**外部调用示例（前端 Ajax）**：
```javascript
// 快递员放置包裹后点击入库
const resp = await fetch('/station/scan_in', {method:'POST'});
const result = await resp.json();
if (result.code === 200) {
    alert(`入库成功，货柜号：${result.data.cabinet_number}`);
}
```

**注意事项**：
- 货物摄像头与人脸识别共用同一设备，前端开发时应保证驿站端进行扫描操作时，客户体验端暂不触发人脸抓拍，避免冲突。
- TODO：包裹操作日志目前未在此端点记录，后续可扩展专用包裹审计表。
```
