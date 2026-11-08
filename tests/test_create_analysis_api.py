from types import SimpleNamespace

import chess.engine
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import main
from backend.app.services.game_analysis import GameNotFoundError


@pytest.fixture
def analysis_service(monkeypatch):
    state = SimpleNamespace(factory=object(), calls=[], error=None)
    settings = SimpleNamespace(stockfish_path="test-stockfish")

    def analyze(game_id, *, session_factory, engine_path, depth):
        assert session_factory is state.factory
        state.calls.append((game_id, engine_path, depth))
        if state.error is not None:
            raise state.error
        return 42

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: state.factory)
    monkeypatch.setitem(main.app.dependency_overrides, main.get_settings, lambda: settings)
    monkeypatch.setattr(main, "analyze_saved_game", analyze)
    return state


@pytest.mark.parametrize("body, depth", [({}, 12), ({"depth": 1}, 1), ({"depth": 20}, 20), ({"depth": 8}, 8)])
def test_create_analysis_returns_201_and_forwards_arguments(analysis_service, body, depth):
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", json=body)
    assert response.status_code == 201
    assert response.json() == {"analysis_id": 42, "game_id": 7}
    assert analysis_service.calls == [(7, "test-stockfish", depth)]


@pytest.mark.parametrize("depth", [0, -1, 21, True, False, "12", 12.0, 1.5, None])
def test_create_analysis_rejects_invalid_depth(analysis_service, depth):
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", json={"depth": depth})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "depth"]
    assert analysis_service.calls == []


@pytest.mark.parametrize("game_id", ["0", "-1", "abc", "1.5"])
def test_create_analysis_rejects_invalid_game_id(analysis_service, game_id):
    with TestClient(main.app) as client:
        response = client.post(f"/games/{game_id}/analyses", json={})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "game_id"]
    assert analysis_service.calls == []


@pytest.mark.parametrize("field", ["dept", "engine_path"])
def test_create_analysis_rejects_unexpected_fields(analysis_service, field):
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", json={field: "unexpected"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    assert analysis_service.calls == []


@pytest.mark.parametrize("body", [None, [], "text"])
def test_create_analysis_requires_object_body(analysis_service, body):
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", json=body)
    assert response.status_code == 422
    assert analysis_service.calls == []


def test_create_analysis_rejects_malformed_json(analysis_service):
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", content='{"depth":', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert analysis_service.calls == []


@pytest.mark.parametrize("error, status, detail", [
    (GameNotFoundError("private details"), 404, "Game not found."),
    (SQLAlchemyError("private SQL"), 503, "Game analysis storage is temporarily unavailable."),
    (chess.engine.EngineError("private engine details"), 503, "The chess engine is temporarily unavailable."),
    (chess.engine.EngineTerminatedError("process died"), 503, "The chess engine is temporarily unavailable."),
    (FileNotFoundError("private executable path"), 503, "The chess engine is temporarily unavailable."),
    (OSError("private OS details"), 503, "The chess engine is temporarily unavailable."),
    (TimeoutError("private timeout details"), 503, "The chess engine is temporarily unavailable."),
    (ValueError("invalid private PGN"), 500, "The saved game could not be analyzed."),
])
def test_create_analysis_maps_errors_without_exposing_details(analysis_service, error, status, detail):
    analysis_service.error = error
    with TestClient(main.app) as client:
        response = client.post("/games/7/analyses", json={})
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert analysis_service.calls == [(7, "test-stockfish", 12)]
