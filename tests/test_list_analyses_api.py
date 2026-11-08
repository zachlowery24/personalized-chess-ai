from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import main


@pytest.fixture
def listing(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], closed=[], missing=False, failure=None, rows=[])

    @contextmanager
    def factory():
        if state.failure == "open":
            raise SQLAlchemyError("private details")
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def lookup(session, game_id):
        assert session is state.session
        state.calls.append(("lookup", game_id))
        if state.failure == "lookup":
            raise SQLAlchemyError("private details")
        return None if state.missing else SimpleNamespace(id=game_id)

    def query(session, game_id, *, limit, offset):
        assert session is state.session
        assert not state.closed
        state.calls.append(("list", game_id, limit, offset))
        if state.failure == "list":
            raise SQLAlchemyError("private details")
        return state.rows

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_game_by_id", lookup)
    monkeypatch.setattr(main, "list_game_analyses", query)
    return state


def test_list_analyses_returns_metadata_in_repository_order(listing):
    listing.rows = [SimpleNamespace(id=i, game_id=7, engine_name="Test Engine", requested_depth=12,
                                   created_at=datetime(2026, 1, 1, tzinfo=UTC)) for i in [9, 3]]
    with TestClient(main.app) as client:
        response = client.get("/games/7/analyses")
    assert response.status_code == 200
    assert response.json() == [dict(analysis_id=i, game_id=7, engine_name="Test Engine",
                                    requested_depth=12, created_at="2026-01-01T00:00:00Z") for i in [9, 3]]
    assert listing.calls == [("lookup", 7), ("list", 7, 20, 0)]
    assert listing.closed == [True]


@pytest.mark.parametrize("limit, offset", [(1, 0), (100, 5)])
def test_list_analyses_accepts_pagination_and_empty_results(listing, limit, offset):
    with TestClient(main.app) as client:
        response = client.get("/games/7/analyses", params={"limit": limit, "offset": offset})
    assert response.status_code == 200
    assert response.json() == []
    assert listing.calls == [("lookup", 7), ("list", 7, limit, offset)]


def test_list_analyses_missing_game_skips_listing(listing):
    listing.missing = True
    with TestClient(main.app) as client:
        response = client.get("/games/7/analyses")
    assert response.status_code == 404
    assert response.json() == {"detail": "Game not found."}
    assert listing.calls == [("lookup", 7)]
    assert listing.closed == [True]


@pytest.mark.parametrize("game_id, params", [
    ("0", {}), ("-1", {}), ("abc", {}), ("1.5", {}),
    ("7", {"limit": 0}), ("7", {"limit": -1}), ("7", {"limit": 101}),
    ("7", {"limit": "abc"}), ("7", {"limit": "1.5"}),
    ("7", {"offset": -1}), ("7", {"offset": "abc"}), ("7", {"offset": "1.5"}),
])
def test_list_analyses_rejects_invalid_parameters(listing, game_id, params):
    with TestClient(main.app) as client:
        response = client.get(f"/games/{game_id}/analyses", params=params)
    assert response.status_code == 422
    assert listing.calls == listing.closed == []


@pytest.mark.parametrize("stage", ["open", "lookup", "list"])
def test_list_analyses_handles_database_failure(listing, stage):
    listing.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/games/7/analyses")
    assert response.status_code == 503
    assert response.json() == {"detail": "Saved analyses are temporarily unavailable."}
    assert listing.closed == ([] if stage == "open" else [True])
