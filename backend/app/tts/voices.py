import os
from pathlib import Path
from typing import List, Dict, Any
from app.config import settings


class VoiceManager:
    """Manages available voices in data/voices directory."""

    SUPPORTED_EXTENSIONS = {".wav", ".ogg", ".mp3", ".flac"}

    def __init__(self, voices_dir: Path = settings.VOICES_DIR):
        self.voices_dir = voices_dir

    def list_voices(self) -> List[Dict[str, Any]]:
        """List all available reference voice names and metadata."""
        voices = []

        # Default voice entry
        voices.append(
            {
                "name": settings.CHATTERBOX_DEFAULT_VOICE,
                "file": "default",
                "is_default": True,
            }
        )

        if not self.voices_dir.exists():
            return voices

        for file_path in self.voices_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                voice_name = file_path.stem.lower()
                if voice_name != settings.CHATTERBOX_DEFAULT_VOICE:
                    voices.append(
                        {
                            "name": voice_name,
                            "file": file_path.name,
                            "is_default": False,
                            "size_bytes": file_path.stat().st_size,
                        }
                    )

        return voices
