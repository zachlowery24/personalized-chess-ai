from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app import main



def test_saved_game_returns_404_when_missing(monkeypatch):
    fake_session = object()
    calls = []

    @contextmanager
    def fake_session_factory():
        yield fake_session

    def fake_lookup(session, game_id):
        assert session is fake_session
        calls.append(game_id)
        return None

    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_session_factory,
        lambda: fake_session_factory,
    )
    monkeypatch.setattr(main, "get_game_by_id", fake_lookup)

    with TestClient(main.app) as client:
        response = client.get("/games/123")

    assert response.status_code == 404
    assert response.json() == {"detail": "Game not found."}
    assert calls == [123]

def test_saved_game_returns_stored_fields(monkeypatch):
    fake_session = object()
    session_closed = []

    stored_game = SimpleNamespace(
        id=123,
        source="chess.com",
        source_url="https://www.chess.com/game/live/456",
        white_player_id=10,
        black_player_id=20,
        white_result="win",
        black_result="resigned",
        time_class="blitz",
        rules="chess",
        ended_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        pgn='[Result "1-0"]\n\n1. e4 e5 1-0',
        created_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )

    @contextmanager
    def fake_session_factory():
        try:
            yield fake_session
        finally:
            session_closed.append(True)

    def fake_lookup(session, game_id):
        assert session is fake_session
        assert game_id == 123
        assert not session_closed
        return stored_game

    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_session_factory,
        lambda: fake_session_factory,
    )
    monkeypatch.setattr(main, "get_game_by_id", fake_lookup)

    with TestClient(main.app) as client:
        response = client.get("/games/123")

    assert response.status_code == 200
    assert response.json() == {
        "id": 123,
        "source": "chess.com",
        "source_url": "https://www.chess.com/game/live/456",
        "white_player_id": 10,
        "black_player_id": 20,
        "white_result": "win",
        "black_result": "resigned",
        "time_class": "blitz",
        "rules": "chess",
        "ended_at": "2026-01-01T12:00:00Z",
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
        "created_at": "2026-01-02T12:00:00Z",
    }
    assert session_closed == [True]


@pytest.mark.parametrize("game_id", ["0", "-1", "abc", "1.5"])
def test_saved_game_rejects_invalid_id_before_database_access(monkeypatch, game_id):
    def unexpected_access(*args, **kwargs):
        pytest.fail("Invalid IDs must not open a session or query games")

    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_session_factory,
        lambda: unexpected_access,
    )
    monkeypatch.setattr(main, "get_game_by_id", unexpected_access)

    with TestClient(main.app) as client:
        response = client.get(f"/games/{game_id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "game_id"]


@pytest.mark.parametrize("failure_stage", ["open", "query"])
def test_saved_game_handles_database_failure(monkeypatch, failure_stage):
    fake_session = object()
    closed = []
    calls = []
    error = OperationalError("SELECT private_data", {}, Exception("private details"))

    @contextmanager
    def fake_session_factory():
        if failure_stage == "open":
            raise error
        try:
            yield fake_session
        finally:
            closed.append(True)

    def fake_lookup(session, game_id):
        assert session is fake_session
        calls.append(game_id)
        raise error

    monkeypatch.setitem(
        main.app.dependency_overrides,
        main.get_session_factory,
        lambda: fake_session_factory,
    )
    monkeypatch.setattr(main, "get_game_by_id", fake_lookup)

    with TestClient(main.app) as client:
        response = client.get("/games/123")

    assert response.status_code == 503
    # Internal SQL and connection details must not appear in the API response.
    assert response.json() == {"detail": "Saved games are temporarily unavailable."}
    assert calls == ([123] if failure_stage == "query" else [])
    assert closed == ([True] if failure_stage == "query" else [])
