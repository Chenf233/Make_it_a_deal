from datetime import date, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel

from database.models import ParcelDailyCounterRepository
from database.schemas import APIResponse
from services.huawei_iot import huawei_iot
from services.huawei_iot.daily_report import daily_parcel_reports

router = APIRouter(prefix="/iot", tags=["Huawei IoT"])


class DailySyncRequest(BaseModel):
    business_date: date | None = None
    force: bool = False


@router.get("/daily-counters", response_model=APIResponse)
async def daily_counters(business_date: date | None = Query(None)):
    if business_date:
        return APIResponse(data=ParcelDailyCounterRepository.get(business_date))
    return APIResponse(data=ParcelDailyCounterRepository.list_before(daily_parcel_reports.today()))


@router.post("/daily-sync", response_model=APIResponse)
async def daily_sync(payload: DailySyncRequest):
    business_date = payload.business_date or daily_parcel_reports.today() - timedelta(days=1)
    try:
        result = await daily_parcel_reports.sync_date(business_date, payload.force)
        return APIResponse(message="日结同步完成", data=result)
    except ValueError as exc:
        return APIResponse(code=400, message=str(exc))
    except Exception as exc:
        return APIResponse(code=500, message=f"日结同步失败：{str(exc)}")


@router.get("/status", response_model=APIResponse)
async def iot_status():
    return APIResponse(data=huawei_iot.get_status())
