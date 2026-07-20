from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PORT: int = 3001
    JWT_SECRET: str = "supersecretjwtsecretkeysharkhub123!"
    DATABASE_API_URL: str = "http://localhost:3000"

    # Mail configuration
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
