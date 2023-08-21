from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    bot_token: SecretStr
    bot_name: str
    google_cx: SecretStr
    google_api_key: SecretStr

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

CONFIG = Settings()