from pydantic import BaseSettings, SecretStr

class Settings(BaseSettings):
    bot_token: SecretStr
    openssl_root: str
    temp_dir: str

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

CONFIG = Settings()