import asyncio
import json
import logging
from typing import Tuple, Optional, Dict

from core.state import app_state
from database.models import ParcelRepository, UserRepository, AccessLogRepository
from services.face_recognition.constants import SIMILARITY_THRESHOLD
from services.camera_manager.constants import DEMO_OVERLAY_ENABLED
from services.hardware_manager import close_user_cabinet
from services.scanner.generator import generate_qr_image

logger = logging.getLogger("SmartStation")


class PickupHandler:
    """
    包裹确取处理器。
    协调人脸再验证、QR 扫描、归属验证与数据库状态更新，并提供取件日志记录。
    """

    async def handle_pickup(self) -> Tuple[bool, str, Optional[Dict]]:
        """
        执行一次取件确认流程：
        1. 人脸识别 + 身份推断（不再依赖前端传入 user_id）
        2. 获取用户待取包裹列表
        3. [演示模式] 生成 QR → 叠加到摄像头画面 → 真实解码
           [正式模式] 摄像头抓帧 → 直接解码
        4. 校验包裹归属 → 更新状态 → 记录日志
        """

        # ---- 阶段 1：人脸识别 + 身份推断 ----
        success, frame = app_state.camera.get_frame()
        if not success or frame is None:
            return False, "摄像头抓图失败", None

        embedding = await asyncio.get_event_loop().run_in_executor(
            None, app_state.face_recognizer.extract_feature, frame)
        if embedding is None:
            return False, "未检测到人脸，请正对摄像头并重试", None

        user_id = app_state.search_face(embedding, threshold=SIMILARITY_THRESHOLD)
        if not user_id:
            return False, "人脸验证失败：未在系统中找到您的信息", None

        user = UserRepository.get_user_by_id(user_id)
        if not user or not user.get("is_active"):
            return False, "用户状态异常", None

        # ---- 阶段 2：获取待取包裹 ----
        active_parcels = ParcelRepository.get_active_parcels_by_phone(user["phone"])
        if not active_parcels:
            return False, "您没有待取包裹", None

        target_parcel = active_parcels[0]

        # ---- 阶段 3：QR 扫描 ----
        extra = target_parcel.get("extra_info") or {}
        if isinstance(extra, str):
            extra = json.loads(extra)

        if DEMO_OVERLAY_ENABLED:
            qr_data = {
                "tracking_no": target_parcel["tracking_no"],
                "company": extra.get("company", "未知"),
                "receiver_name": user["username"],
                "receiver_phone": user["phone"],
            }
            qr_img = generate_qr_image(qr_data)
            app_state.camera.set_overlay_qr(qr_img)

            try:
                # 让 MJPEG 流有足够帧展示 QR 叠加画面
                await asyncio.sleep(0.8)

                ok, scan_frame = app_state.camera.get_frame()
                if not ok or scan_frame is None:
                    return False, "摄像头抓图失败", None

                if not app_state.scanner:
                    return False, "扫描器未就绪", None

                _, data_list = app_state.scanner.scan(scan_frame, skip_demo=True)
            finally:
                app_state.camera.set_overlay_qr(None)

            tracking_no = None
            if data_list:
                tracking_no = data_list[0].get("tracking_no")
        else:
            if not app_state.scanner:
                return False, "扫描器未就绪", None
            _, data_list = app_state.scanner.scan(frame)

            tracking_no = None
            if data_list:
                tracking_no = data_list[0].get("tracking_no")

        if not tracking_no:
            return False, "未检测到包裹二维码，请将包裹码对准摄像头并重试", None

        # ---- 阶段 4：归属校验 & 出库 ----
        matched = None
        for p in active_parcels:
            if p["tracking_no"] == tracking_no:
                matched = p
                break

        if not matched:
            return False, f"未找到属于您的包裹单号 {tracking_no}，请确认", None

        ok = ParcelRepository.update_parcel_status(matched["parcel_id"], 2)
        if not ok:
            return False, "包裹已被取走，请确认", None

        AccessLogRepository.add_log(
            user_id=user_id,
            action_type="PICKUP",
            snapshot_path="",
            picked_parcels=[tracking_no]
        )

        logger.info(f"用户 {user_id} 确认取件 {tracking_no}，状态已更新")

        try:
            close_user_cabinet(user_id, matched["cabinet_number"])
        except Exception:
            logger.exception("关闭柜号 %s 硬件失败", matched["cabinet_number"])

        return True, f"取件成功：{tracking_no}", {
            "parcel_id": matched["parcel_id"],
            "tracking_no": tracking_no,
            "cabinet_number": matched["cabinet_number"]
        }

    @staticmethod
    def check_exit_status(user_id: int) -> dict:
        """
        查询出口确认信息：应取/已取/未取包裹统计。
        返回 {"expected_total": int, "picked_count": int, "active_parcels": list}
        """
        user = UserRepository.get_user_by_id(user_id)
        if not user:
            return {"expected_total": 0, "picked_count": 0, "active_parcels": []}

        all_parcels = ParcelRepository.get_all_parcels_by_phone(user["phone"])
        active = [p for p in all_parcels if p["status"] == 1]
        picked = [p for p in all_parcels if p["status"] == 2]

        return {
            "expected_total": len(all_parcels),
            "picked_count": len(picked),
            "active_parcels": active
        }
