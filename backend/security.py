from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from db import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGO = "HS256"

def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, h: str) -> bool:
    if h.startswith("$2"):
        return pwd_context.verify(p, h)
    # 开发临时：数据库里存明文
    return p == h

def create_access_token(data: dict, minutes: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=minutes or settings.JWT_EXPIRE_MINUTES)
    payload = {**data, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGO])
    except JWTError:
        raise ValueError("Invalid token")
