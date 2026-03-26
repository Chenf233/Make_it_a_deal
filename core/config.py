from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SmartStation AI"
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置
    DB_URL: str = "sqlite+aiosqlite:///./smart_station.db"
    
    # 驿站业务配置
    CAMERA_INDEX: int = 0
    
    class Config:
        env_file = ".env"

settings = Settings()