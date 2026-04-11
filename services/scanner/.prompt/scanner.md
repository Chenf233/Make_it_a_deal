# 模块：scanner (二维码/条码识别)
**职责**：提供纯粹的图像二维码/条码生成与解码能力，不涉及任何数据库或硬件直接调用。支持演示模式(Mock)。

**输出数据协议 (Schema)**：
当解码成功时，返回的列表中每个字典包含以下固定字段（用于无缝对接 Database 模块）：
- `tracking_no` (str): 唯一快递单号 (如 "SF0412120800")
- `company` (str): 快递公司名称 (如 "顺丰速运")
- `receiver_name` (str): 收件人姓名
- `receiver_phone` (str): 收件人手机号
- `status` (int): 包裹状态 (如 1 表示在库)
- `in_time` (str): 模拟的入库时间格式 "YYYY-MM-DD HH:MM:SS"

**接口**：
- 暴露 `QRScanner` 类用于对单帧图像进行解码和框选绘制。
- 暴露 `QRGenerator` 类用于将字典数据生成为二维码图片。

**外部调用示例**：
```python
from services.scanner import QRScanner
scanner = QRScanner()
processed_frame, results = scanner.scan(frame)