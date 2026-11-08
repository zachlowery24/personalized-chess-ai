from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import main

from backend.app.models.game import Game
from backend.app.models.player import PlayerProfile
from backend.app.models.game_analysis import GameAnalysis as StoredAnalysis
from backend.app.models.move_analysis import MoveAnalysis as StoredMove
from backend.app.repositories.games import get_or_create_game
from backend.app.services import game_analysis as service
from backend.app.services.engine_analysis import GameAnalysis, MoveAnalysis, PositionAnalysis
from backend.app.services.pgn import extract_move_positions, parse_pgn_games


@pytest.fixture
def committed_game(db_engine):
    factory = sessionmaker(bind=db_engine)
    token = uuid4().hex
    names = [f"white_{token}", f"black_{token}"]
    url = f"https://www.chess.com/game/live/{token}"
    try:
        with factory.begin() as session:
            game = get_or_create_game(session, {
                "url": url, "white": {"username": names[0], "result": "win"},
                "black": {"username": names[1], "result": "resigned"},
                "rules": "chess", "time_class": "blitz", "end_time": 1234567890,
                "pgn": "1. e4 e5 1-0",
            })
            game_id = game.id
        yield factory, game_id
    finally:
        with factory.begin() as session:
            games = select(Game.id).where(Game.source_url == url)
            runs = select(StoredAnalysis.id).where(StoredAnalysis.game_id.in_(games))
            session.execute(delete(StoredMove).where(StoredMove.game_analysis_id.in_(runs)))
            session.execute(delete(StoredAnalysis).where(StoredAnalysis.game_id.in_(games)))
            session.execute(delete(Game).where(Game.source_url == url))
            session.execute(delete(PlayerProfile).where(PlayerProfile.username.in_(names)))


def fake_analysis(pgn, *, engine_path, depth):
    assert engine_path == "test-engine"
    positions = extract_move_positions(parse_pgn_games(pgn)[0])
    score = PositionAnalysis(None, 0, None, depth)
    return GameAnalysis("Test Engine", depth, [
        MoveAnalysis(**position, before=score, after=score, centipawn_loss=0)
        for position in positions
    ])


def test_saved_analysis_commits_runs_and_moves(committed_game, monkeypatch):
    factory, game_id = committed_game
    monkeypatch.setattr(service, "analyze_game", fake_analysis)
    ids = []
    for depth in [8, 12]:
        run_id = service.analyze_saved_game(game_id, session_factory=factory, engine_path="test-engine", depth=depth)
        ids.append(run_id)
        # An independent session proves the service committed before returning.
        with factory() as session:
            run = session.get(StoredAnalysis, run_id)
            assert (run.game_id, run.engine_name, run.requested_depth) == (game_id, "Test Engine", depth)
            rows = session.scalars(select(StoredMove).where(StoredMove.game_analysis_id == run_id).order_by(StoredMove.ply)).all()
            assert [row.uci for row in rows] == ["e2e4", "e7e5"]
    assert ids[0] != ids[1]


def test_failed_analysis_write_rolls_back_run_and_moves(committed_game, monkeypatch):
    factory, game_id = committed_game
    monkeypatch.setattr(service, "analyze_game", fake_analysis)
    existing = service.analyze_saved_game(game_id, session_factory=factory, engine_path="test-engine")

    def invalid_analysis(*args, **kwargs):
        result = fake_analysis(*args, **kwargs)
        return replace(result, moves=[result.moves[0], replace(result.moves[1], ply=1)])

    monkeypatch.setattr(service, "analyze_game", invalid_analysis)
    with pytest.raises(IntegrityError):
        service.analyze_saved_game(game_id, session_factory=factory, engine_path="test-engine")
    with factory() as session:
        assert session.scalars(select(StoredAnalysis.id).where(StoredAnalysis.game_id == game_id)).all() == [existing]
        rows = session.scalars(select(StoredMove).join(StoredAnalysis).where(StoredAnalysis.game_id == game_id)).all()
        assert len(rows) == 2
        assert all(row.game_analysis_id == existing for row in rows)


def test_api_creates_and_retrieves_committed_analysis(committed_game, monkeypatch):
    factory, game_id = committed_game
    engine_calls = []

    def analyze(pgn, *, engine_path, depth):
        engine_calls.append((pgn, engine_path, depth))
        return fake_analysis(pgn, engine_path=engine_path, depth=depth)

    monkeypatch.setattr(service, "analyze_game", analyze)
    monkeypatch.setitem(main.app.dependency_overrides, main.get_session_factory, lambda: factory)
    monkeypatch.setitem(main.app.dependency_overrides, main.get_settings,
                        lambda: SimpleNamespace(stockfish_path="test-engine"))

    with TestClient(main.app) as client:
        created = client.post(f"/games/{game_id}/analyses", json={"depth": 8})
        assert created.status_code == 201, created.text
        run_id = created.json()["analysis_id"]
        assert created.json() == {"analysis_id": run_id, "game_id": game_id}

        # A separate database session verifies persistence before the GET.
        with factory() as session:
            run = session.get(StoredAnalysis, run_id)
            assert run is not None
            created_at = run.created_at

        retrieved = client.get(f"/analyses/{run_id}")
        assert retrieved.status_code == 200, retrieved.text
        body = retrieved.json()
        assert datetime.fromisoformat(body.pop("created_at")) == created_at
        expected_moves = []
        for move in fake_analysis("1. e4 e5 1-0", engine_path="test-engine", depth=8).moves:
            fields = {name: getattr(move, name) for name in (
                "ply", "color", "uci", "san", "fen_before", "fen_after", "centipawn_loss",
            )}
            for side in ("before", "after"):
                for name in ("best_move", "score_cp", "mate_in", "depth"):
                    fields[f"{side}_{name}"] = getattr(getattr(move, side), name)
            expected_moves.append(fields)
        assert body == {
            "analysis_id": run_id, "game_id": game_id,
            "engine_name": "Test Engine", "requested_depth": 8,
            "moves": expected_moves,
            "white_summary": dict(color="white", total_moves=1, scored_moves=1,
                                  unscored_moves=0, average_centipawn_loss=0.0),
            "black_summary": dict(color="black", total_moves=1, scored_moves=1,
                                  unscored_moves=0, average_centipawn_loss=0.0),
        }
        assert client.get(f"/analyses/{run_id}").json() == retrieved.json()

    # Reading saved results must not invoke engine analysis again.
    assert engine_calls == [("1. e4 e5 1-0", "test-engine", 8)]
