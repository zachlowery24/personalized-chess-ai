from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import main
from backend.app.schemas.practice import PracticePositionResponse, PracticeQueueResponse


@pytest.fixture
def practice_api(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], closed=[], missing=False, failure=None)
    state.queue = PracticeQueueResponse(player_id=7, analyzed_game_count=2, positions=[
        PracticePositionResponse(game_id=3, analysis_id=4, ply=2, color="black",
                                 fen="test position", engine_name="Test Engine", requested_depth=12),
    ])

    @contextmanager
    def factory():
        if state.failure == "open":
            raise SQLAlchemyError("private connection details")
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def lookup(session, player_id):
        assert session is state.session
        state.calls.append(("lookup", player_id))
        if state.failure == "lookup":
            raise SQLAlchemyError("private SQL")
        return None if state.missing else SimpleNamespace(id=player_id)

    def build(session, player_id, *, limit):
        assert session is state.session
        assert not state.closed
        state.calls.append(("queue", player_id, limit))
        if state.failure == "queue":
            raise SQLAlchemyError("private SQL")
        return state.queue

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_player_by_id", lookup)
    monkeypatch.setattr(main, "build_practice_queue", build)
    return state


@pytest.mark.parametrize("params, expected_limit", [({}, 3), ({"limit": 1}, 1), ({"limit": 10}, 10)])
def test_practice_returns_queue_without_answers(practice_api, params, expected_limit):
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice", params=params)
    assert response.status_code == 200
    assert response.json() == {
        "player_id": 7, "analyzed_game_count": 2,
        "positions": [{"game_id": 3, "analysis_id": 4, "ply": 2, "color": "black",
                       "fen": "test position", "engine_name": "Test Engine", "requested_depth": 12}],
    }
    assert practice_api.calls == [("lookup", 7), ("queue", 7, expected_limit)]
    assert practice_api.closed == [True]


def test_practice_existing_player_can_have_empty_queue(practice_api):
    practice_api.queue = PracticeQueueResponse(player_id=7, analyzed_game_count=0, positions=[])
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice")
    assert response.status_code == 200
    assert response.json() == {"player_id": 7, "analyzed_game_count": 0, "positions": []}


def test_practice_missing_player_does_not_build_queue(practice_api):
    practice_api.missing = True
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice")
    assert response.status_code == 404
    assert response.json() == {"detail": "Player not found."}
    assert practice_api.calls == [("lookup", 7)]
    assert practice_api.closed == [True]


@pytest.mark.parametrize("player_id, params, location", [
    ("0", {}, ["path", "player_id"]), ("-1", {}, ["path", "player_id"]),
    ("abc", {}, ["path", "player_id"]), ("1.5", {}, ["path", "player_id"]),
    *[("7", {"limit": value}, ["query", "limit"]) for value in [0, -1, 11, "abc", "1.5"]],
])
def test_practice_invalid_parameters_skip_database(practice_api, player_id, params, location):
    with TestClient(main.app) as client:
        response = client.get(f"/players/{player_id}/practice", params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == location
    assert practice_api.calls == practice_api.closed == []


@pytest.mark.parametrize("stage", ["open", "lookup", "queue"])
def test_practice_database_errors_are_sanitized(practice_api, stage):
    practice_api.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice")
    assert response.status_code == 503
    assert response.json() == {"detail": "Practice positions are temporarily unavailable."}
    assert practice_api.closed == ([] if stage == "open" else [True])
