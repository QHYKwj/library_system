from datetime import datetime, timedelta
from jose import jwt, JWTError
from db import settings
import hashlib

ALGO = "HS256"

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def hash_password(p: str) -> str:
    """
    大作业简化：使用 SHA-256 + salt（这里用 JWT_SECRET 当 salt）
    返回格式：sha256$<hex>
    """
    salt = settings.JWT_SECRET or "dev_salt"
    return "sha256$" + _sha256_hex(f"{salt}|{p}")

def verify_password(p: str, h: str) -> bool:
    """
    支持：
    - sha256$...（新方案）
    - 纯明文（你原来的开发临时逻辑，兼容旧库）
    - bcrypt（如果你库里还有旧 bcrypt hash，直接判 False，避免炸）
    """
    if not h:
        return False

    # 新方案
    if h.startswith("sha256$"):
        return hash_password(p) == h

    # 旧 bcrypt（现在不用了，直接返回 False；你要兼容旧用户就必须迁移/重置密码）
    if h.startswith("$2"):
        return False

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
