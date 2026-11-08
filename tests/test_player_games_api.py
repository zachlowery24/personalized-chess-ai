from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app import main


@pytest.fixture
def listing(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], closed=[], games=[], failure=None)

    @contextmanager
    def factory():
        if state.failure == "open":
            raise OperationalError("private SQL", {}, Exception("private details"))
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def lookup(session, player_id, *, limit, offset, time_class):
        assert session is state.session
        assert not state.closed
        state.calls.append((player_id, limit, offset, time_class))
        if state.failure == "query":
            raise OperationalError("private SQL", {}, Exception("private details"))
        return state.games

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "list_games_for_player", lookup)
    return state


def test_player_games_returns_serialized_games_in_repository_order(listing):
    expected = []
    for game_id in [8, 3]:
        fields = dict(
            id=game_id, source="chess.com", source_url=f"https://www.chess.com/game/live/{game_id}",
            white_player_id=10, black_player_id=20, white_result="win",
            black_result="resigned", time_class="blitz", rules="chess",
            ended_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            pgn='[Result "1-0"]\n\n1. e4 e5 1-0',
        )
        listing.games.append(SimpleNamespace(**fields))
        expected.append({**fields, "ended_at": "2026-01-01T00:00:00Z",
                         "created_at": "2026-01-02T00:00:00Z"})

    with TestClient(main.app) as client:
        response = client.get("/players/10/games")

    assert response.status_code == 200
    assert response.json() == expected
    assert listing.calls == [(10, 20, 0, None)]
    assert listing.closed == [True]


@pytest.mark.parametrize("time_class", ["bullet", "blitz", "rapid", "daily"])
@pytest.mark.parametrize("limit", [1, 100])
def test_player_games_forwards_valid_filters_and_returns_empty(listing, time_class, limit):
    with TestClient(main.app) as client:
        response = client.get("/players/10/games", params={
            "time_class": time_class, "limit": limit, "offset": 7,
        })
    assert response.status_code == 200
    assert response.json() == []
    assert listing.calls == [(10, limit, 7, time_class)]
    assert listing.closed == [True]


@pytest.mark.parametrize("player_id, params, location", [
    ("0", {}, ["path", "player_id"]),
    ("-1", {}, ["path", "player_id"]),
    ("abc", {}, ["path", "player_id"]),
    ("1.5", {}, ["path", "player_id"]),
    ("10", {"limit": 0}, ["query", "limit"]),
    ("10", {"limit": -1}, ["query", "limit"]),
    ("10", {"limit": 101}, ["query", "limit"]),
    ("10", {"limit": "abc"}, ["query", "limit"]),
    ("10", {"limit": "1.5"}, ["query", "limit"]),
    ("10", {"offset": -1}, ["query", "offset"]),
    ("10", {"offset": "abc"}, ["query", "offset"]),
    ("10", {"offset": "1.5"}, ["query", "offset"]),
    ("10", {"time_class": "classical"}, ["query", "time_class"]),
    ("10", {"time_class": "Blitz"}, ["query", "time_class"]),
    ("10", {"time_class": ""}, ["query", "time_class"]),
])
def test_player_games_rejects_invalid_parameters(listing, player_id, params, location):
    with TestClient(main.app) as client:
        response = client.get(f"/players/{player_id}/games", params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == location
    assert listing.calls == []
    assert listing.closed == []


@pytest.mark.parametrize("stage", ["open", "query"])
def test_player_games_handles_database_failure(listing, stage):
    listing.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/players/10/games")
    assert response.status_code == 503
    assert response.json() == {"detail": "Saved games are temporarily unavailable."}
    assert listing.calls == ([(10, 20, 0, None)] if stage == "query" else [])
    assert listing.closed == ([True] if stage == "query" else [])
