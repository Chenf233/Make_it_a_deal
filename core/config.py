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

    class Config:
        env_file = ".env"

# 导出全局单例配置
settings = Settings()