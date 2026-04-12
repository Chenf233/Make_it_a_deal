# 文件：generator.py
**职责**：封装 `qrcode` 库，将标准的包裹字典数据转化为 JSON 字符串并生成二维码图像文件，用于模拟驿站入库前的打印流程。
**接口**：
- `generate_qr(parcel_data: dict, filename: str)`: 过滤数据并生成图片。
**外部调用示例**：
```python
from services.scanner import generate_qr
generate_qr({"tracking_no": "SF123", "company": "顺丰"}, "test.png")