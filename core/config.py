# 文件：core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- FastAPI 基础元数据 ---
    APP_NAME: str = "SmartStation - 智能无人驿站自取系统"
    VERSION: str = "1.0.0"
    DEBUG_MODE: bool = True

    # --- 网络与安全配置 ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"] # 允许跨域的列表，开发环境暂设为全部

    # --- 华为云 IoT C 子进程 ---
    HUAWEI_IOT_ENABLED: bool = True
    HUAWEI_IOT_EXECUTABLE: str = "services/huaweicloud-iot-device-sdk-c-master-mine/station_iotd"
    HUAWEI_IOT_CONFIG: str = "services/huaweicloud-iot-device-sdk-c-master-mine/station_iotd.json"
    HUAWEI_IOT_REQUEST_TIMEOUT: float = 5.0
    HUAWEI_IOT_DAILY_SERVICE_ID: str = "Station_1"
    HUAWEI_IOT_DAILY_PROPERTY_A: str = "A_parcels_per_D"
    HUAWEI_IOT_DAILY_PROPERTY_B: str = "B_parcels_per_D"
    HUAWEI_IOT_BUSINESS_TIMEZONE: str = "Asia/Shanghai"

    class Config:
        env_file = ".env"

# 导出全局单例配置
settings = Settings()
