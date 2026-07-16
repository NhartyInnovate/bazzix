from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")


settings = Settings()