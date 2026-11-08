from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app import main


@pytest.fixture
def replay(monkeypatch):
    state = SimpleNamespace(session=object(), closed=[], calls=[], failure=None,
                            game=SimpleNamespace(pgn="1. e4 e5 *"), parsed=[])

    @contextmanager
    def factory():
        if state.failure == "open":
            raise OperationalError("private SQL", {}, Exception("private details"))
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def lookup(session, game_id):
        assert session is state.session
        state.calls.append(game_id)
        if state.failure == "query":
            raise OperationalError("private SQL", {}, Exception("private details"))
        return state.game

    real_build = main.build_game_moves

    def build(text):
        assert state.closed == [True]
        state.parsed.append(text)
        return real_build(text)

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_game_by_id", lookup)
    monkeypatch.setattr(main, "build_game_moves", build)
    return state


def test_moves_endpoint_replays_after_session_closes(replay):
    with TestClient(main.app) as client:
        response = client.get("/games/12/moves")
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == 12
    assert [move["uci"] for move in body["moves"]] == ["e2e4", "e7e5"]
    assert body["moves"][0]["fen_after"] == body["moves"][1]["fen_before"]
    assert replay.calls == [12]
    assert replay.parsed == ["1. e4 e5 *"]


def test_moves_endpoint_missing_game(replay):
    replay.game = None
    with TestClient(main.app) as client:
        response = client.get("/games/12/moves")
    assert response.status_code == 404
    assert response.json() == {"detail": "Game not found."}
    assert replay.closed == [True]
    assert replay.parsed == []


@pytest.mark.parametrize("game_id", ["0", "-1", "abc", "1.5"])
def test_moves_endpoint_rejects_invalid_id(replay, game_id):
    with TestClient(main.app) as client:
        response = client.get(f"/games/{game_id}/moves")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "game_id"]
    assert replay.calls == replay.closed == replay.parsed == []


@pytest.mark.parametrize("stage", ["open", "query"])
def test_moves_endpoint_database_failure(replay, stage):
    replay.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/games/12/moves")
    assert response.status_code == 503
    assert response.json() == {"detail": "Saved games are temporarily unavailable."}
    assert replay.closed == ([True] if stage == "query" else [])
    assert replay.parsed == []


@pytest.mark.parametrize("pgn", ["", "1. e4 e5 2. Bh6 *"])
def test_moves_endpoint_invalid_stored_pgn(replay, pgn):
    replay.game.pgn = pgn
    with TestClient(main.app) as client:
        response = client.get("/games/12/moves")
    assert response.status_code == 500
    assert response.json() == {"detail": "The saved game could not be replayed."}
    assert replay.closed == [True]
