import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.api.routes import router, queue_manager
from app.twitch.bot import TwitchChatListener
from app.websocket.server import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("twitchtts.main")

twitch_listener = TwitchChatListener(queue_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown handlers."""
    logger.info("Starting TwitchTTS Server Core...")
    twitch_listener.start()
    yield
    logger.info("Shutting down TwitchTTS Server Core...")
    twitch_listener.stop()


app = FastAPI(
    title="TwitchTTS - High-Performance Multi-Voice Speech System",
    description="The ultimate Twitch TTS system with inline multi-voice chat readback.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local dashboards and OBS Studio browser sources
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time Dashboard & OBS state updates."""
    await ws_manager.connect(websocket)
    # Immediately send current state upon connection
    await websocket.send_json(
        {"type": "QUEUE_UPDATE", "data": queue_manager.get_queue_state()}
    )
    try:
        while True:
            data = await websocket.receive_text()
            # Respond to client ping/heartbeat
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# Locate static frontend directory (checks root frontend/ first, then app/static)
static_path = settings.BASE_DIR / "frontend"
if not static_path.exists():
    static_path = Path(__file__).parent / "static"
if not static_path.exists():
    static_path = Path(__file__).parent.parent / "frontend"


# Explicit frontend HTML routes for direct URL navigation & OBS browser source overlays
@app.get("/overlay", include_in_schema=False)
@app.get("/overlay/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
@app.get("/widget", include_in_schema=False)
@app.get("/widget/", include_in_schema=False)
async def serve_spa_route():
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="Index HTML file not found")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon fallback endpoint."""
    favicon_file = static_path / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(favicon_file)
    return Response(status_code=204)


# Mount static frontend directory at root (MUST be placed after explicit API/HTML routes)
if static_path.exists():
    logger.info(f"Mounting static frontend from: {static_path}")
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
else:
    logger.warning("No static frontend directory found!")


