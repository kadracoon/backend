import os

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.db import get_pool
from app.db.sql import DDL


# from app.api import auth
from app.core.mongo import mongo_db

# from app.api.auth import router as auth_router
# from app.api.game import router as game_router


app = FastAPI(
    title="Kadracoon Backend",
    version="0.1.0"
)

# app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/")
async def root():
    return {"message": "Hello, Kadracoon!"}


@app.on_event("startup")
async def startup():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(DDL)


@app.get("/ping-mongo")
async def ping_mongo():
    mongo_uri = os.getenv("MONGO_URI")
    db_name = mongo_uri.rsplit("/", 1)[-1]  # вытаскиваем 'tmdb' из URI
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    collections = await db.list_collection_names()
    return {"collections": collections}



# app.include_router(auth_router, prefix="/auth")
# app.include_router(game_router, prefix="/game")
