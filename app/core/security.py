from datetime import datetime, timedelta
from jose import jwt
import bcrypt
import os


JWT_SECRET = os.getenv("JWT_SECRET", "super-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 1 день


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_jwt_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
