import re
from typing import List, Dict, Any, Optional
from app.config import settings


class TextNormalizer:
    """
    Normalizes text messages and extracts multi-voice segments.
    Supports inline voice tags like:
      - [brian] Hello world!
      - [voice=narrator] Once upon a time...
      - Hey! [lisa] How are you? [bob] I am fine!
    """

    # Matches [voice_name] or [voice=voice_name]
    VOICE_TAG_REGEX = re.compile(r"\[(?:voice=)?([a-zA-Z0-9_\-]+)\]", re.IGNORECASE)
    URL_REGEX = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    REPEATED_CHARS_REGEX = re.compile(r"(.)\1{4,}")

    def __init__(self, default_voice: Optional[str] = None):
        self.default_voice = default_voice or settings.CHATTERBOX_DEFAULT_VOICE

    def clean_text(self, text: str) -> str:
        """Clean URLs, spam characters, and excess whitespace."""
        if not text:
            return ""

        # Filter URLs
        if settings.ENABLE_URL_FILTER:
            text = self.URL_REGEX.sub(" link ", text)

        # Reduce repeated character spam (e.g., "Loooooool" -> "Lool")
        if settings.ENABLE_SPAM_FILTER:
            text = self.REPEATED_CHARS_REGEX.sub(r"\1\1", text)

        # Profanity censoring
        if settings.PROFANITY_FILTER_ENABLED and settings.BLOCKED_WORDS:
            for word in settings.BLOCKED_WORDS:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                text = pattern.sub("***", text)

        # Clean extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Enforce max length per segment
        if len(text) > settings.MAX_TEXT_LENGTH:
            text = text[: settings.MAX_TEXT_LENGTH] + "..."

        return text

    def split_into_phrases(self, text: str) -> List[str]:
        """Splits a text string into short phrase/sentence chunks for rapid pipelined synthesis."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        # Split on sentence terminals or clause punctuation (. ! ? ; \n)
        raw_phrases = re.split(r"(?<=[.!?;\n])\s+", cleaned)
        phrases = []

        for phrase in raw_phrases:
            phrase = phrase.strip()
            if not phrase:
                continue

            # If phrase is still long (> 80 chars), split on commas
            if len(phrase) > 80:
                sub_parts = re.split(r"(?<=[,])\s+", phrase)
                for sub in sub_parts:
                    sub = sub.strip()
                    if sub:
                        phrases.append(sub)
            else:
                phrases.append(phrase)

        return phrases or [cleaned]

    def parse_multi_voice_message(
        self, raw_text: str, override_default_voice: Optional[str] = None, chop_phrases: bool = True
    ) -> List[Dict[str, str]]:
        """
        Parses a message into voice segments and optionally chops long segments into phrase chunks.
        Returns a list of dicts: [{'voice': str, 'text': str}]
        """
        current_default = override_default_voice or self.default_voice
        matches = list(self.VOICE_TAG_REGEX.finditer(raw_text))

        raw_segments = []
        if not matches:
            cleaned = self.clean_text(raw_text)
            if cleaned:
                raw_segments.append({"voice": current_default, "text": cleaned})
        else:
            last_idx = 0
            current_voice = current_default

            for match in matches:
                start, end = match.span()
                preceding_text = raw_text[last_idx:start]
                cleaned_preceding = self.clean_text(preceding_text)
                if cleaned_preceding:
                    raw_segments.append({"voice": current_voice, "text": cleaned_preceding})

                current_voice = match.group(1).lower()
                last_idx = end

            trailing_text = raw_text[last_idx:]
            cleaned_trailing = self.clean_text(trailing_text)
            if cleaned_trailing:
                raw_segments.append({"voice": current_voice, "text": cleaned_trailing})

        if not chop_phrases:
            return raw_segments

        # Chop raw segments into sub-phrases for low latency streaming synthesis
        final_segments = []
        for seg in raw_segments:
            phrases = self.split_into_phrases(seg["text"])
            for p in phrases:
                final_segments.append({"voice": seg["voice"], "text": p})

        return final_segments

