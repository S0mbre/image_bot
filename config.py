from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
import logging
from pathlib import Path
from typing import Optional

# ============================================================ #

ENC = 'utf-8'

# ============================================================ #

class Settings(BaseSettings):
    debug: Optional[bool] = False
    redis: Optional[bool] = True
    bot_token: SecretStr
    bot_name: str
    google_cx: SecretStr
    google_api_key: SecretStr
    yandex_api_key: SecretStr
    webhook_secret: SecretStr
    base_webhook_url: str

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding=ENC)

CONFIG = Settings()

# логи направляем в файл `log.log` ...
logging.basicConfig(filename=str(Path(__file__).parent / 'log.log'), filemode='w', style='{',
                    format='[{asctime}] [{levelname}] {message}', datefmt='%d.%m.%Y %H:%M:%S',
                    encoding=ENC, level=logging.DEBUG if CONFIG.debug else logging.INFO)
# ...а также в консоль (`stderr`)
logging.getLogger().addHandler(logging.StreamHandler())