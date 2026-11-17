from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import main


@pytest.fixture
def reveal(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], closed=[], missing=None, failure=None)

    @contextmanager
    def factory():
        if state.failure == "open":
            raise SQLAlchemyError("private details")
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def candidate(session, player_id, analysis_id, ply):
        assert session is state.session
        state.calls.append(("move", player_id, analysis_id, ply))
        if state.failure == "move":
            raise SQLAlchemyError("private SQL")
        return None if state.missing == "move" else SimpleNamespace(
            ply=ply, color="black", fen_before="test position", uci="e7e5",
            before_best_move="c7c5", centipawn_loss=80,
        )

    def analysis(session, analysis_id):
        assert session is state.session
        assert not state.closed
        state.calls.append(("analysis", analysis_id))
        if state.failure == "analysis":
            raise SQLAlchemyError("private SQL")
        return None if state.missing == "analysis" else SimpleNamespace(
            id=analysis_id, game_id=9, engine_name="Test Engine", requested_depth=12,
        )

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_practice_candidate", candidate)
    monkeypatch.setattr(main, "get_game_analysis_by_id", analysis)
    return state


def test_reveal_returns_saved_answer(reveal):
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice/4/2/reveal")
    assert response.status_code == 200
    assert response.json() == dict(game_id=9, analysis_id=4, ply=2, color="black",
        fen="test position", played_move="e7e5", recommended_move="c7c5",
        centipawn_loss=80, engine_name="Test Engine", requested_depth=12)
    assert reveal.calls == [("move", 7, 4, 2), ("analysis", 4)]
    assert reveal.closed == [True]


@pytest.mark.parametrize("missing", ["move", "analysis"])
def test_reveal_missing_records_return_404(reveal, missing):
    reveal.missing = missing
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice/4/2/reveal")
    assert response.status_code == 404
    assert response.json() == {"detail": "Practice position not found."}
    assert reveal.closed == [True]
    if missing == "move":
        assert reveal.calls == [("move", 7, 4, 2)]


@pytest.mark.parametrize("field", ["player_id", "analysis_id", "ply"])
@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_reveal_rejects_invalid_ids_before_database_access(reveal, field, value):
    ids = dict(player_id="7", analysis_id="4", ply="2")
    ids[field] = value
    with TestClient(main.app) as client:
        response = client.get(f'/players/{ids["player_id"]}/practice/{ids["analysis_id"]}/{ids["ply"]}/reveal')
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", field]
    assert reveal.calls == reveal.closed == []


@pytest.mark.parametrize("stage", ["open", "move", "analysis"])
def test_reveal_database_failure(reveal, stage):
    reveal.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/players/7/practice/4/2/reveal")
    assert response.status_code == 503
    assert response.json() == {"detail": "Practice positions are temporarily unavailable."}
    assert reveal.closed == ([] if stage == "open" else [True])
