# utils/config.py
import json
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='settings.env', env_file_encoding='utf-8', extra='ignore')

    MAIN_SHEET_ID: str
    MAIN_SHEET_NAME: str
    GOOGLE_KEY_PATH: str

    HEADER_KEY_COLUMNS_JSON: str = '["CHECK", "Product_name", "Product_pack"]'
    SLEEP_TIME: int = 5
    BASE_URL: str = 'https://sosanhsach.io.vn/eneba-api/graphql/'
    AUTH_URL: str = 'https://sosanhsach.io.vn/eneba-auth/oauth/token'

    CLIENT_ID: str
    AUTH_ID: str
    AUTH_SECRET: str
    WORKERS: Optional[float] = 1
    @property
    def HEADER_KEY_COLUMNS(self) -> List[str]:
        """Chuyển đổi chuỗi JSON của các cột key thành một danh sách Python."""
        return json.loads(self.HEADER_KEY_COLUMNS_JSON)


# Tạo một instance duy nhất để import và sử dụng trong toàn bộ dự án
settings = Settings()
