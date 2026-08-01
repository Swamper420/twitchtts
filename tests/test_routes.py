import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)


def test_get_voices():
    response = client.get("/api/voices")
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert len(data["voices"]) >= 1


def test_get_queue():
    response = client.get("/api/queue")
    assert response.status_code == 200
    data = response.json()
    assert "queue" in data
    assert "count" in data


def test_tts_missing_text():
    response = client.get("/api/tts")
    assert response.status_code == 400
    assert "text" in response.json()["detail"].lower()


@patch("app.api.routes.tts_client.synthesize", new_callable=AsyncMock)
def test_tts_get_spec(mock_synth):
    mock_synth.return_value = {
        "audio_bytes": b"OggOpusDummyAudioData",
        "format": "ogg",
        "content_type": "audio/ogg",
        "json_data": None,
    }
    response = client.get("/api/tts?text=Terve%20maailma!")
    assert response.status_code == 200
    assert response.content == b"OggOpusDummyAudioData"
    assert "audio/ogg" in response.headers["content-type"]


@patch("app.api.routes.tts_client.synthesize", new_callable=AsyncMock)
def test_tts_post_json_spec(mock_synth):
    mock_synth.return_value = {
        "audio_bytes": b"DummyWavData",
        "format": "json",
        "content_type": "application/json",
        "json_data": None,
    }
    response = client.get("/api/tts?text=Hello&format=json")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["text"] == "Hello"
    assert "audio" in json_data


def test_spa_routes():
    for route in ["/", "/overlay", "/dashboard", "/widget", "/style.css", "/app.js"]:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} returned {resp.status_code}"
    
    favicon_resp = client.get("/favicon.ico")
    assert favicon_resp.status_code in (200, 204)

