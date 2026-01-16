import os
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

class Settings(BaseSettings):
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "library_db"

    JWT_SECRET: str = "please_change_me"
    JWT_EXPIRE_MINUTES: int = 720

    ALGOLIA_APP_ID: str = ""
    ALGOLIA_ADMIN_KEY: str = ""
    ALGOLIA_INDEX: str = "books_index"

    class Config:
        env_file = ".env"

settings = Settings()

MYSQL_DSN = (
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
    "?charset=utf8mb4"
)

engine = create_engine(MYSQL_DSN, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
