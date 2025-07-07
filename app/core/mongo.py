from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings


mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
mongo_db = mongo_client["kadracoon"]
