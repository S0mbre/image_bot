from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
import logging
from pathlib import Path

# ============================================================ #

ENC = 'utf-8'

# ============================================================ #

class Settings(BaseSettings):
    debug: bool
    bot_token: SecretStr
    bot_name: str
    google_cx: SecretStr
    google_api_key: SecretStr
    yandex_api_key: SecretStr

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding=ENC)

CONFIG = Settings()

logging.basicConfig(filename=str(Path(__file__).parent / 'log.log'), filemode='w', style='{',
                    format='[{asctime}] [{levelname}] {message}', datefmt='%d.%m.%Y %H:%M:%S',
                    encoding=ENC, level=logging.DEBUG if CONFIG.debug else logging.INFO)