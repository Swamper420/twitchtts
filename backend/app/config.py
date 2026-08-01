import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    # TTS API Configuration (Target Chatterbox API)
    CHATTERBOX_API_URL: str = "http://localhost:8080/api/tts"
    CHATTERBOX_API_MODEL: str = "default"
    CHATTERBOX_DEFAULT_VOICE: str = "default"
    DEFAULT_AUDIO_FORMAT: str = "ogg"  # ogg, wav, pcm, json

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    VOICES_DIR: Path = BASE_DIR / "data" / "voices"
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"

    # Twitch Configuration
    TWITCH_CHANNEL: str = ""
    TWITCH_BOT_NICK: str = "justinfan12345"  # Anonymous default Twitch nick
    TWITCH_OAUTH_TOKEN: str = ""
    TWITCH_READ_ALL_CHAT: bool = True
    TWITCH_COMMAND_PREFIX: str = "!"

    # Queue & Filter Settings
    MAX_QUEUE_SIZE: int = 100
    MAX_TEXT_LENGTH: int = 400
    ENABLE_SPAM_FILTER: bool = True
    ENABLE_URL_FILTER: bool = True
    PROFANITY_FILTER_ENABLED: bool = False
    BLOCKED_WORDS: list[str] = []

    # Server Settings
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

# Ensure required data directories exist
settings.VOICES_DIR.mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
