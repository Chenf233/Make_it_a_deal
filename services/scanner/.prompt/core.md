# 文件：core.py
**职责**：封装 `pyzbar` 解析逻辑，负责从单帧 NumPy 数组中寻找二维码，提取 JSON 数据，并在原图上绘制 Bounding Box。内部不维持任何状态和冷却时间。
**接口**：
- `scan(frame: np.ndarray) -> Tuple[np.ndarray, List[dict]]`: 输入图像，返回绘制后的图像及解析出的字典列表。
**外部调用示例**：
```python
scanner = QRScanner()
annotated_img, data_list = scanner.scan(image_np)
if data_list:
    print("Found QRs:", data_list)