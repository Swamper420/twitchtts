import base64
import logging
from typing import Optional, Dict, Any, Union
import httpx
from app.config import settings

logger = logging.getLogger("twitchtts.tts_client")


class TTSClient:
    """
    Async client for Chatterbox TTS API endpoints.
    Spec:
      HTTP Methods: GET or POST (/api/tts)
      Parameters:
        - text (string, required): Text string to synthesize.
        - model (string, optional): Model engine override (defaults to CHATTERBOX_API_MODEL).
        - voice (string, optional): Reference voice in data/voices/ (defaults to CHATTERBOX_DEFAULT_VOICE).
        - format (string, optional): Output audio format — "ogg" / "opus" (default), "wav", "pcm", or "json".
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.CHATTERBOX_API_URL).rstrip("/")

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None,
        audio_format: Optional[str] = None,
        use_post: bool = True,
    ) -> Dict[str, Any]:
        """
        Synthesize text using Chatterbox TTS API.
        Returns a dict with audio_bytes, format, content_type, and base64_audio if json.
        """
        target_voice = voice or settings.CHATTERBOX_DEFAULT_VOICE
        target_model = model or settings.CHATTERBOX_API_MODEL
        target_format = audio_format or settings.DEFAULT_AUDIO_FORMAT

        payload = {
            "text": text,
            "voice": target_voice,
            "model": target_model,
            "format": target_format,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            if use_post:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            else:
                response = await client.get(self.base_url, params=payload)

            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if target_format.lower() == "json" or "application/json" in content_type:
                data = response.json()
                audio_b64 = data.get("audio") or data.get("data") or ""
                audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""
                return {
                    "audio_bytes": audio_bytes,
                    "format": data.get("format", target_format),
                    "content_type": "audio/ogg" if target_format == "ogg" else "audio/wav",
                    "json_data": data,
                }
            else:
                return {
                    "audio_bytes": response.content,
                    "format": target_format,
                    "content_type": content_type or f"audio/{target_format}",
                    "json_data": None,
                }
