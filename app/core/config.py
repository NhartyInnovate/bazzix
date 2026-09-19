from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


class Settings:
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL = os.getenv("DATABASE_URL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    )
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080").rstrip("/")
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081",
        ).split(",")
        if origin.strip()
    ]
    MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", 100000))
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 4000))
    
    # Payment Provider Configuration
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")


settings = Settings()