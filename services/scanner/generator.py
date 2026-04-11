import json
import qrcode
from services.scanner.constants import (
    DEFAULT_QR_VERSION, DEFAULT_BOX_SIZE, 
    DEFAULT_BORDER, DEFAULT_SAVE_PATH
)

def generate_qr(parcel_data: dict, filename: str = DEFAULT_SAVE_PATH) -> bool:
    """
    将包裹信息生成二维码图片
    :param parcel_data: 包含包裹信息的字典
    :param filename: 保存的文件路径
    :return: 成功返回 True
    """
    try:
        # 剥离可能存在的自增ID，只保留业务数据
        data_to_encode = {k: v for k, v in parcel_data.items() if k != "parcel_id"}
        json_str = json.dumps(data_to_encode, ensure_ascii=False, separators=(',', ':'))
        
        qr = qrcode.QRCode(
            version=DEFAULT_QR_VERSION, 
            error_correction=qrcode.constants.ERROR_CORRECT_H, 
            box_size=DEFAULT_BOX_SIZE, 
            border=DEFAULT_BORDER
        )
        qr.add_data(json_str)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        return True
    except Exception as e:
        print(f"⚠️ QR Generate Error: {e}")
        return False