import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.api import collections, game
# from app.api import sets as sets_api
from app.core.db import get_pool
from app.core.mongo import mongo_db
from app.db.sql import DDL

# from app.api.auth import router as auth_router
# from app.api.game import router as game_router


app = FastAPI(
    title="Kadracoon Backend",
    version="0.1.0"
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://kadracoon-frontend.vercel.app",
    "https://kadracoon.fun",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # можно ["*"] на время dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(auth.router, prefix="/auth", tags=["auth"])
# app.include_router(collections.router)
app.include_router(collections.router)
app.include_router(game.router)
# app.include_router(game_api.router)
# app.include_router(sets_api.router)


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
