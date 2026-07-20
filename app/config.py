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

    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = ""
    BREVO_SENDER_NAME: str = "Panda BW Barbershop"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
