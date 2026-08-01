import asyncio
import uuid
import time
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.tts.client import TTSClient
from app.tts.normalizer import TextNormalizer

logger = logging.getLogger("twitchtts.queue")


class QueueItem:
    """Represents a queued TTS message event."""

    def __init__(
        self,
        user: str,
        raw_text: str,
        segments: List[Dict[str, str]],
        message_id: Optional[str] = None,
        source: str = "chat",
    ):
        self.id = message_id or str(uuid.uuid4())
        self.user = user
        self.raw_text = raw_text
        self.segments = segments  # List of {'voice': str, 'text': str}
        self.audio_segments: List[Dict[str, Any]] = []
        self.status = "queued"  # queued, synthesizing, ready, playing, completed, skipped
        self.created_at = time.time()
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user": self.user,
            "raw_text": self.raw_text,
            "segments": self.segments,
            "status": self.status,
            "created_at": self.created_at,
            "source": self.source,
            "audio_count": len(self.audio_segments),
        }


class TTSQueueManager:
    """Manages multi-voice TTS priority queue and async synthesis pipeline."""

    def __init__(self, tts_client: TTSClient, normalizer: TextNormalizer):
        self.tts_client = tts_client
        self.normalizer = normalizer
        self.queue: List[QueueItem] = []
        self.history: List[QueueItem] = []
        self.current_item: Optional[QueueItem] = None
        self.ws_broadcast_callback = None
        self._lock = asyncio.Lock()

    def set_ws_callback(self, callback):
        self.ws_broadcast_callback = callback

    async def _notify_state_change(self):
        if self.ws_broadcast_callback:
            await self.ws_broadcast_callback(self.get_queue_state())

    async def add_message(
        self,
        user: str,
        raw_text: str,
        user_default_voice: Optional[str] = None,
        source: str = "chat",
    ) -> Optional[QueueItem]:
        """Parse multi-voice message, synthesize audio for each segment, and enqueue."""
        segments = self.normalizer.parse_multi_voice_message(
            raw_text, override_default_voice=user_default_voice
        )
        if not segments:
            logger.info(f"Skipping empty/filtered message from {user}: '{raw_text}'")
            return None

        item = QueueItem(
            user=user,
            raw_text=raw_text,
            segments=segments,
            source=source,
        )

        async with self._lock:
            if len(self.queue) >= settings.MAX_QUEUE_SIZE:
                logger.warning("Queue full! Dropping oldest item.")
                self.queue.pop(0)

            self.queue.append(item)

        # Trigger synthesis asynchronously
        asyncio.create_task(self._synthesize_item(item))
        await self._notify_state_change()
        return item

    async def _synthesize_item(self, item: QueueItem):
        """Synthesize phrase chunks for a queue item in a low-latency pipeline."""
        item.status = "synthesizing"
        await self._notify_state_change()

        async def _synth_segment(idx: int, segment: Dict[str, str]):
            try:
                result = await self.tts_client.synthesize(
                    text=segment["text"],
                    voice=segment["voice"],
                )
                return {
                    "index": idx,
                    "voice": segment["voice"],
                    "text": segment["text"],
                    "audio_bytes": result["audio_bytes"],
                    "format": result["format"],
                    "content_type": result["content_type"],
                }
            except Exception as e:
                logger.error(
                    f"Synthesis failed for phrase '{segment['text']}' with voice '{segment['voice']}': {e}"
                )
                return None

        # Synthesize first chunk immediately for low-latency playback start
        if item.segments:
            first_chunk = await _synth_segment(0, item.segments[0])
            if first_chunk:
                item.audio_segments.append(first_chunk)
                item.status = "ready"
                await self._notify_state_change()

        # Concurrently synthesize remaining phrase chunks in parallel pipeline
        if len(item.segments) > 1:
            tasks = [
                _synth_segment(idx, seg)
                for idx, seg in enumerate(item.segments[1:], start=1)
            ]
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    item.audio_segments.append(res)

            # Sort audio segments by original phrase order
            item.audio_segments.sort(key=lambda x: x["index"])
            await self._notify_state_change()


    async def pop_next(self) -> Optional[QueueItem]:
        """Pop the next ready item to play."""
        async with self._lock:
            if not self.queue:
                self.current_item = None
                return None

            # Find first ready item or wait for top item
            first_ready = next((i for i in self.queue if i.status == "ready"), None)
            if first_ready:
                self.queue.remove(first_ready)
                first_ready.status = "playing"
                self.current_item = first_ready
                await self._notify_state_change()
                return first_ready

            return None

    async def finish_item(self, item_id: str):
        """Mark item completed and move to history."""
        async with self._lock:
            if self.current_item and self.current_item.id == item_id:
                self.current_item.status = "completed"
                self.history.insert(0, self.current_item)
                if len(self.history) > 50:
                    self.history.pop()
                self.current_item = None
                await self._notify_state_change()

    async def skip_current(self):
        """Skip current playing item."""
        async with self._lock:
            if self.current_item:
                self.current_item.status = "skipped"
                self.history.insert(0, self.current_item)
                self.current_item = None
                await self._notify_state_change()

    async def clear_queue(self):
        """Clear all queued items."""
        async with self._lock:
            self.queue.clear()
            await self._notify_state_change()

    def get_queue_state(self) -> Dict[str, Any]:
        """Returns current queue state snapshot."""
        return {
            "current": self.current_item.to_dict() if self.current_item else None,
            "queue": [item.to_dict() for item in self.queue],
            "history": [item.to_dict() for item in self.history[:10]],
            "count": len(self.queue),
        }
