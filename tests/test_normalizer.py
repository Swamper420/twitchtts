import pytest
from app.tts.normalizer import TextNormalizer


def test_single_voice_message():
    normalizer = TextNormalizer(default_voice="default")
    segments = normalizer.parse_multi_voice_message("Hello world this is a test.")
    assert len(segments) == 1
    assert segments[0]["voice"] == "default"
    assert segments[0]["text"] == "Hello world this is a test."


def test_multi_voice_message():
    normalizer = TextNormalizer(default_voice="default")
    raw = "Hey everyone! [brian] This is Brian speaking. [narrator] And this is the narrator."
    segments = normalizer.parse_multi_voice_message(raw)
    assert len(segments) == 3

    assert segments[0]["voice"] == "default"
    assert segments[0]["text"] == "Hey everyone!"

    assert segments[1]["voice"] == "brian"
    assert segments[1]["text"] == "This is Brian speaking."

    assert segments[2]["voice"] == "narrator"
    assert segments[2]["text"] == "And this is the narrator."


def test_voice_syntax_with_equals():
    normalizer = TextNormalizer(default_voice="default")
    raw = "[voice=sam] Welcome back! [voice=lisa] Hope you enjoy!"
    segments = normalizer.parse_multi_voice_message(raw)
    assert len(segments) == 2
    assert segments[0]["voice"] == "sam"
    assert segments[0]["text"] == "Welcome back!"
    assert segments[1]["voice"] == "lisa"
    assert segments[1]["text"] == "Hope you enjoy!"


def test_spam_and_url_filtering():
    normalizer = TextNormalizer(default_voice="default")
    raw = "Check out https://twitch.tv and Loooooooooool"
    cleaned = normalizer.clean_text(raw)
    assert "https://" not in cleaned
    assert "link" in cleaned
    assert "Lool" in cleaned


def test_phrase_chopping():
    normalizer = TextNormalizer(default_voice="default")
    raw = "Hello everyone! Hope you are having an awesome day. Check out this clip!"
    phrases = normalizer.split_into_phrases(raw)
    assert len(phrases) == 3
    assert phrases[0] == "Hello everyone!"
    assert phrases[1] == "Hope you are having an awesome day."
    assert phrases[2] == "Check out this clip!"


def test_multi_voice_with_phrase_chopping():
    normalizer = TextNormalizer(default_voice="default")
    raw = "Welcome back! [brian] Check this out! It is super cool."
    segments = normalizer.parse_multi_voice_message(raw, chop_phrases=True)
    assert len(segments) == 3
    assert segments[0]["voice"] == "default"
    assert segments[0]["text"] == "Welcome back!"
    assert segments[1]["voice"] == "brian"
    assert segments[1]["text"] == "Check this out!"
    assert segments[2]["voice"] == "brian"
    assert segments[2]["text"] == "It is super cool."

