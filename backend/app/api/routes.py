import base64
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Response, Depends
from pydantic import BaseModel

from app.config import settings
from app.tts.client import TTSClient
from app.tts.voices import VoiceManager
from app.tts.normalizer import TextNormalizer
from app.queue.manager import TTSQueueManager
from app.websocket.server import ws_manager

router = APIRouter()

# Singletons shared across routes
tts_client = TTSClient()
voice_manager = VoiceManager()
normalizer = TextNormalizer()
queue_manager = TTSQueueManager(tts_client, normalizer)

# Register WS broadcast callback
queue_manager.set_ws_callback(
    lambda state: ws_manager.broadcast_json({"type": "QUEUE_UPDATE", "data": state})
)


class TTSRequest(BaseModel):
    text: str
    model: Optional[str] = None
    voice: Optional[str] = None
    format: Optional[str] = None


class EnqueueRequest(BaseModel):
    user: str = "Streamer"
    text: str
    voice: Optional[str] = None


class SettingsRequest(BaseModel):
    twitch_channel: Optional[str] = None
    twitch_bot_nick: Optional[str] = None
    chatterbox_api_url: Optional[str] = None
    chatterbox_default_voice: Optional[str] = None


@router.api_route("/api/tts", methods=["GET", "POST"])
async def handle_tts(
    request_data: Optional[TTSRequest] = None,
    text: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    voice: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
):
    """
    HTTP Methods: GET or POST (/api/tts)
    Parameters:
      text (string, required): Text string to synthesize.
      model (string, optional): Model engine override.
      voice (string, optional): Reference voice.
      format (string, optional): Output audio format — "ogg" / "opus" (default), "wav", "pcm", or "json".
    """
    req_text = (request_data.text if request_data else None) or text
    if not req_text:
        raise HTTPException(status_code=400, detail="Missing required parameter: text")

    req_model = (request_data.model if request_data else None) or model or settings.CHATTERBOX_API_MODEL
    req_voice = (request_data.voice if request_data else None) or voice or settings.CHATTERBOX_DEFAULT_VOICE
    req_format = (request_data.format if request_data else None) or format or settings.DEFAULT_AUDIO_FORMAT

    try:
        result = await tts_client.synthesize(
            text=req_text,
            voice=req_voice,
            model=req_model,
            audio_format=req_format,
        )

        if req_format.lower() == "json":
            audio_b64 = base64.b64encode(result["audio_bytes"]).decode("utf-8")
            return {
                "text": req_text,
                "voice": req_voice,
                "model": req_model,
                "format": "ogg" if req_format == "ogg" else req_format,
                "mime": result["content_type"],
                "audio": audio_b64,
            }

        return Response(
            content=result["audio_bytes"],
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="speech.{req_format}"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {str(e)}")


@router.get("/api/voices")
async def get_voices():
    """List available reference voices."""
    return {"voices": voice_manager.list_voices()}


@router.get("/api/queue")
async def get_queue():
    """Get current TTS queue state."""
    return queue_manager.get_queue_state()


@router.post("/api/queue/add")
async def add_to_queue(payload: EnqueueRequest):
    """Manually enqueue a TTS message (supports inline multi-voice syntax)."""
    item = await queue_manager.add_message(
        user=payload.user,
        raw_text=payload.text,
        user_default_voice=payload.voice,
        source="manual",
    )
    if not item:
        raise HTTPException(status_code=400, detail="Message empty or filtered.")
    return item.to_dict()


@router.post("/api/queue/skip")
async def skip_queue():
    """Skip currently playing TTS item."""
    await queue_manager.skip_current()
    return {"status": "success"}


@router.post("/api/queue/clear")
async def clear_queue():
    """Clear all queued TTS items."""
    await queue_manager.clear_queue()
    return {"status": "success"}


@router.get("/api/queue/audio/{item_id}/{segment_index}")
async def get_queue_audio(item_id: str, segment_index: int):
    """Retrieve audio binary payload for a specific phrase segment of a queue item."""
    item = None
    if queue_manager.current_item and queue_manager.current_item.id == item_id:
        item = queue_manager.current_item
    else:
        item = next((i for i in queue_manager.queue if i.id == item_id), None)

    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")

    segment = next((s for s in item.audio_segments if s.get("index", 0) == segment_index), None)
    if not segment:
        raise HTTPException(status_code=404, detail="Audio phrase segment not found or pending.")

    return Response(
        content=segment["audio_bytes"],
        media_type=segment["content_type"],
    )



@router.get("/api/settings")
async def get_settings():
    return {
        "chatterbox_api_url": settings.CHATTERBOX_API_URL,
        "chatterbox_api_model": settings.CHATTERBOX_API_MODEL,
        "chatterbox_default_voice": settings.CHATTERBOX_DEFAULT_VOICE,
        "twitch_channel": settings.TWITCH_CHANNEL,
        "twitch_bot_nick": settings.TWITCH_BOT_NICK,
        "read_all_chat": settings.TWITCH_READ_ALL_CHAT,
    }


@router.post("/api/settings")
async def update_settings(payload: SettingsRequest):
    if payload.twitch_channel is not None:
        settings.TWITCH_CHANNEL = payload.twitch_channel
    if payload.twitch_bot_nick is not None:
        settings.TWITCH_BOT_NICK = payload.twitch_bot_nick
    if payload.chatterbox_api_url is not None:
        settings.CHATTERBOX_API_URL = payload.chatterbox_api_url
        tts_client.base_url = payload.chatterbox_api_url.rstrip("/")
    if payload.chatterbox_default_voice is not None:
        settings.CHATTERBOX_DEFAULT_VOICE = payload.chatterbox_default_voice

    return {"status": "success", "settings": await get_settings()}
