# Reference Voices Directory

Place reference audio files (`.wav`, `.ogg`, `.mp3`, `.flac`) in this directory.

The voice file name (without extension) will automatically be recognized as a voice identifier in inline speech tags:
e.g. If you place `brian.wav` or `narrator.mp3` in `data/voices/`:
- Twitch chatters can use `[brian] Hello!` or `[narrator] Once upon a time...`
- The system automatically passes `voice="brian"` or `voice="narrator"` to the Chatterbox `/api/tts` endpoint.
