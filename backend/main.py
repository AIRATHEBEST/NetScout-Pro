"""
NetScout Backend — FastAPI application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import create_tables, get_db
from db.redis_client import close_redis
from api.devices import router as devices_router
from api.scans import router as scans_router
from api.ws import agent_websocket_handler, dashboard_websocket_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NetScout Backend...")
    await create_tables()
    logger.info("Database tables ready")
    yield
    await close_redis()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="NetScout API",
    version="1.0.0",
    description="Real-time network scanning and monitoring platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(devices_router)
app.include_router(scans_router)


# WebSocket: agent connection
@app.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await agent_websocket_handler(websocket, db)


# WebSocket: dashboard connection
@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await dashboard_websocket_handler(websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "NetScout Backend"}


@app.get("/")
async def root():
    return {"message": "NetScout API", "version": "1.0.0", "docs": "/docs"}
