import logging
from typing import Tuple, Optional, Dict

from core.state import app_state
from database.models import ParcelRepository, UserRepository, AccessLogRepository

logger = logging.getLogger("SmartStation")


class PickupHandler:
    """
    包裹确取处理器。
    协调摄像头帧捕获、QR 扫描、归属验证与数据库状态更新，并提供取件日志记录。
    """

    async def handle_pickup(self, user_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """
        执行一次取件确认流程：
        1. 抓取摄像头当前帧
        2. 使用 QRScanner 解码条码
        3. 校验包裹是否属于当前用户（通过 receiver_phone 匹配）
        4. 更新包裹状态为“已取件” (status=2)
        5. 记录取件日志 (action_type="PICKUP")
        返回: (是否成功, 消息, 包裹信息字典或 None)
        """
        # 1. 抓帧
        success, frame = app_state.camera.get_frame()
        if not success or frame is None:
            return False, "摄像头抓图失败", None

        # 2. 解码 QR
        if not app_state.scanner:
            return False, "扫描器未就绪", None
        annotated_img, data_list = app_state.scanner.scan(frame)

        if not data_list:
            return False, "未检测到有效二维码", None

        qr_data = data_list[0]   # 一帧仅处理一个包裹码
        tracking_no = qr_data.get("tracking_no")
        if not tracking_no:
            return False, "二维码数据缺少快递单号", None

        # 3. 验证包裹归属
        user = UserRepository.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在", None
        receiver_phone = user["phone"]

        # TODO: 当包裹数量大时，建议在 ParcelRepository 中新增 get_parcel_by_tracking_no 方法以提升性能
        active_parcels = ParcelRepository.get_active_parcels_by_phone(receiver_phone)
        target_parcel = None
        for p in active_parcels:
            if p["tracking_no"] == tracking_no:
                target_parcel = p
                break

        if not target_parcel:
            return False, f"未找到属于您的包裹单号 {tracking_no}，请确认", None

        # 4. 更新状态为已取件
        ParcelRepository.update_parcel_status(target_parcel["parcel_id"], 2)

        # 5. 记录取件日志（action_type="PICKUP"）
        AccessLogRepository.add_log(
            user_id=user_id,
            action_type="PICKUP",
            snapshot_path="",
            picked_parcels=[tracking_no]
        )

        logger.info(f"用户 {user_id} 确认取件 {tracking_no}，状态已更新")

        return True, f"取件成功：{tracking_no}", {
            "parcel_id": target_parcel["parcel_id"],
            "tracking_no": tracking_no,
            "cabinet_number": target_parcel["cabinet_number"]
        }