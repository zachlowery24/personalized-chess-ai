from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app import main


@pytest.fixture
def lookup(monkeypatch):
    state = SimpleNamespace(
        session=object(), calls=[], closed=[], failure=None,
        player=SimpleNamespace(id=12, source="chess.com", username="hikaru",
                               created_at=datetime(2026, 1, 1, tzinfo=UTC)),
    )

    @contextmanager
    def factory():
        if state.failure == "open":
            raise OperationalError("private SQL", {}, Exception("private details"))
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def fake_lookup(session, source, username):
        assert session is state.session
        assert not state.closed
        state.calls.append((source, username))
        if state.failure == "query":
            raise OperationalError("private SQL", {}, Exception("private details"))
        return state.player

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_player_by_username", fake_lookup)
    return state


@pytest.mark.parametrize("params", [
    {"username": " Hikaru "},
    {"username": " Hikaru ", "source": "chess.com"},
])
def test_lookup_returns_profile_and_forwards_parameters(lookup, params):
    with TestClient(main.app) as client:
        response = client.get("/players/lookup", params=params)
    assert response.status_code == 200
    assert response.json() == {
        "id": 12, "source": "chess.com", "username": "hikaru",
        "created_at": "2026-01-01T00:00:00Z",
    }
    # Normalization belongs to the real repository, tested with PostgreSQL.
    assert lookup.calls == [("chess.com", " Hikaru ")]
    assert lookup.closed == [True]


def test_lookup_returns_404_and_closes_session(lookup):
    lookup.player = None
    with TestClient(main.app) as client:
        response = client.get("/players/lookup", params={"username": "missing"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Player not found."}
    assert lookup.calls == [("chess.com", "missing")]
    assert lookup.closed == [True]


@pytest.mark.parametrize("params, field", [
    ({}, "username"),
    ({"username": ""}, "username"),
    ({"username": " \n\t"}, "username"),
    ({"username": "x" * 256}, "username"),
    ({"username": "hikaru", "source": "lichess"}, "source"),
    ({"username": "hikaru", "source": "CHESS.COM"}, "source"),
    ({"username": "hikaru", "source": ""}, "source"),
])
def test_lookup_rejects_invalid_query_without_database_access(lookup, params, field):
    with TestClient(main.app) as client:
        response = client.get("/players/lookup", params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]
    assert lookup.calls == []
    assert lookup.closed == []


@pytest.mark.parametrize("length", [1, 255])
def test_lookup_accepts_username_length_boundaries(lookup, length):
    lookup.player = None
    with TestClient(main.app) as client:
        response = client.get("/players/lookup", params={"username": "x" * length})
    assert response.status_code == 404
    assert lookup.calls == [("chess.com", "x" * length)]


@pytest.mark.parametrize("stage", ["open", "query"])
def test_lookup_handles_database_errors_without_leaking_details(lookup, stage):
    lookup.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/players/lookup", params={"username": "hikaru"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Player profiles are temporarily unavailable."}
    assert lookup.calls == ([("chess.com", "hikaru")] if stage == "query" else [])
    assert lookup.closed == ([True] if stage == "query" else [])
