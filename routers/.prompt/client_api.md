# 文件：client_api.py
**职责**：提供客户体验端交互接口。实现基于人脸检索的刷脸开门、出门核验、防遗漏警报，以及客户端人脸识别视频流。
**接口**：
- `POST /client/access/entry`: 抓拍人脸进行 1:N 极速检索，验证成功记录进门日志，返回 `APIResponse[FaceAuthResult]`（Action为IN，含名下包裹）。
- `POST /client/access/exit`: 抓拍人脸出门，比对在库包裹核验遗漏并触发硬件指令，记录出门日志，返回 `APIResponse[FaceAuthResult]`（Action为OUT）。
- `GET /client/video_feed`: 基于 MJPEG 协议的前端人脸预览流分发。
**外部调用示例**：
```javascript
// 客户站在屏幕前点击刷脸进门
fetch("/client/access/entry", { method: "POST" })
    .then(res => res.json())
    .then(res => {
        if(res.code === 200 && res.data.action === "IN") {
            alert(`欢迎！您有 ${res.data.active_parcels.length} 个包裹`);
        }
    });