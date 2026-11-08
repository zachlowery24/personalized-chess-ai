from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app import main


@pytest.fixture
def retrieval(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], closed=[], failure=None, missing=False)
    state.moves = [dict(
        ply=1, color="white", uci="e2e4", san="e4", fen_before="before", fen_after="after",
        before_best_move="d2d4", before_score_cp=30, before_mate_in=None, before_depth=12,
        after_best_move="e7e5", after_score_cp=30, after_mate_in=None, after_depth=13,
        centipawn_loss=0,
    ), dict(
        ply=2, color="black", uci="e7e5", san="e5", fen_before="after", fen_after="final",
        before_best_move="e7e5", before_score_cp=30, before_mate_in=None, before_depth=13,
        after_best_move=None, after_score_cp=None, after_mate_in=0, after_depth=None,
        centipawn_loss=None,
    )]

    @contextmanager
    def factory():
        if state.failure == "open":
            raise SQLAlchemyError("private database details")
        try:
            yield state.session
        finally:
            state.closed.append(True)

    def lookup(session, analysis_id):
        assert session is state.session
        assert not state.closed
        state.calls.append(("lookup", analysis_id))
        if state.failure == "lookup":
            raise SQLAlchemyError("private SQL")
        return None if state.missing else SimpleNamespace(
            id=analysis_id, game_id=7, engine_name="Test Stockfish", requested_depth=12,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    def moves(session, analysis_id):
        assert session is state.session
        assert not state.closed
        state.calls.append(("moves", analysis_id))
        if state.failure == "moves":
            raise SQLAlchemyError("private SQL")
        return [SimpleNamespace(**move) for move in state.moves]

    def unexpected_engine(*args, **kwargs):
        pytest.fail("Retrieving saved results must not rerun analysis")

    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setattr(main, "get_game_analysis_by_id", lookup)
    monkeypatch.setattr(main, "list_analysis_moves", moves)
    monkeypatch.setattr(main, "analyze_saved_game", unexpected_engine)
    return state


def test_saved_analysis_returns_all_fields_and_nullable_scores(retrieval):
    with TestClient(main.app) as client:
        response = client.get("/analyses/42")
    assert response.status_code == 200
    assert response.json() == dict(
        analysis_id=42, game_id=7, engine_name="Test Stockfish", requested_depth=12,
        created_at="2026-01-01T00:00:00Z", moves=retrieval.moves,
        white_summary=dict(color="white", total_moves=1, scored_moves=1,
                           unscored_moves=0, average_centipawn_loss=0.0),
        black_summary=dict(color="black", total_moves=1, scored_moves=0,
                           unscored_moves=1, average_centipawn_loss=None),
    )
    assert retrieval.calls == [("lookup", 42), ("moves", 42)]
    assert retrieval.closed == [True]


def test_missing_analysis_skips_move_query(retrieval):
    retrieval.missing = True
    with TestClient(main.app) as client:
        response = client.get("/analyses/42")
    assert response.status_code == 404
    assert response.json() == {"detail": "Analysis not found."}
    assert retrieval.calls == [("lookup", 42)]
    assert retrieval.closed == [True]


def test_saved_summary_counts_zero_and_excludes_mate_transitions(retrieval):
    base = retrieval.moves[0]
    retrieval.moves = [
        dict(base, ply=1, centipawn_loss=0),
        dict(base, ply=2, color="black", centipawn_loss=100),
        dict(base, ply=3, centipawn_loss=60),
        dict(base, ply=4, color="black", centipawn_loss=20),
        dict(base, ply=5, after_score_cp=None, after_mate_in=3, centipawn_loss=None),
    ]
    with TestClient(main.app) as client:
        response = client.get("/analyses/42")
    assert response.status_code == 200
    body = response.json()
    assert body["white_summary"] == dict(color="white", total_moves=3,
        scored_moves=2, unscored_moves=1, average_centipawn_loss=30.0)
    assert body["black_summary"] == dict(color="black", total_moves=2,
        scored_moves=2, unscored_moves=0, average_centipawn_loss=60.0)
    assert retrieval.calls == [("lookup", 42), ("moves", 42)]


def test_saved_summary_handles_color_without_moves(retrieval):
    retrieval.moves = retrieval.moves[:1]
    with TestClient(main.app) as client:
        response = client.get("/analyses/42")
    assert response.status_code == 200
    assert response.json()["black_summary"] == dict(color="black", total_moves=0,
        scored_moves=0, unscored_moves=0, average_centipawn_loss=None)


@pytest.mark.parametrize("analysis_id", ["0", "-1", "abc", "1.5"])
def test_invalid_analysis_id_does_not_query_database(retrieval, analysis_id):
    with TestClient(main.app) as client:
        response = client.get(f"/analyses/{analysis_id}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "analysis_id"]
    assert retrieval.calls == retrieval.closed == []


@pytest.mark.parametrize("stage", ["open", "lookup", "moves"])
def test_saved_analysis_database_failure(retrieval, stage):
    retrieval.failure = stage
    with TestClient(main.app) as client:
        response = client.get("/analyses/42")
    assert response.status_code == 503
    assert response.json() == {"detail": "Saved analyses are temporarily unavailable."}
    assert retrieval.closed == ([] if stage == "open" else [True])
