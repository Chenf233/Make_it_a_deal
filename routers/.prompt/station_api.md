# 文件：station_api.py
**职责**：提供驿站工作端（快递员）作业接口。实现货物视觉识别入库自动化，并提供实时货物监控视频流。
**接口**：
- `POST /station/scan_in`: 触发货物摄像头抓帧与条码解析，通过校验后执行入库操作，返回 `APIResponse[ScanResultData]`。
- `GET /station/video_feed`: 基于 MJPEG 协议的货物监控视频流分发。
**外部调用示例**：
```javascript
// 快递员放置包裹后点击入库
fetch("/station/scan_in", { method: "POST" })
    .then(res => res.json())
    .then(res => {
        if(res.code === 200) {
            console.log("入库单号:", res.data.tracking_no);
        }
    });