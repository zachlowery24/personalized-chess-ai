from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.app.repositories.games import get_or_create_game
from backend.app.repositories.analyses import create_game_analysis
from backend.app.repositories.players import get_or_create_player
from backend.app.repositories.practice import list_latest_player_analyses, list_practice_candidates, get_practice_candidate
from backend.app.services.practice import build_practice_queue
from backend.app.services.engine_analysis import GameAnalysis, MoveAnalysis, PositionAnalysis
from backend.app.services.pgn import parse_pgn_games, extract_move_positions


@pytest.fixture
def history(db_session):
    username = f"practice_{uuid4().hex}"
    player = get_or_create_player(db_session, "chess.com", username)

    def make_game(color):
        names = {c: f"opponent_{uuid4().hex}" for c in ("white", "black")}
        if color:
            names[color] = username
        return get_or_create_game(db_session, dict(
            url=f"https://www.chess.com/game/live/{uuid4().hex}",
            white=dict(username=names["white"], result="win"),
            black=dict(username=names["black"], result="resigned"),
            rules="chess", time_class="blitz", end_time=1234567890,
            pgn="1. e4 e5 2. Nf3 Nc6 1-0",
        ))

    def add_run(game, losses, seconds=0, overrides=None):
        positions = extract_move_positions(parse_pgn_games(game.pgn)[0])
        moves = []
        for i, position in enumerate(positions):
            before = PositionAnalysis(["d2d4", "c7c5", "f1c4", "g8f6"][i], 0, None, 12)
            loss = losses[i]
            after = PositionAnalysis(None, None if loss is None else 0, 3 if loss is None else None, 12)
            move = MoveAnalysis(**position, before=before, after=after, centipawn_loss=loss)
            if overrides and i in overrides:
                move = replace(move, before=replace(before, best_move=overrides[i]))
            moves.append(move)
        run = create_game_analysis(db_session, game.id, GameAnalysis("Test Engine", 12, moves))
        run.created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)
        db_session.flush()
        return run

    return player.id, make_game, add_run


def test_latest_runs_use_timestamp_then_id_and_exclude_other_players(db_session, history):
    player_id, game, run = history
    white, black, other = game("white"), game("black"), game(None)
    newest = run(white, [20]*4, seconds=10)
    run(white, [900]*4, seconds=0)  # Higher ID but older timestamp.
    run(black, [10]*4)
    tied_latest = run(black, [30]*4)
    run(other, [999]*4, seconds=20)
    assert {r.id for r in list_latest_player_analyses(db_session, player_id)} == {newest.id, tied_latest.id}


def test_candidates_include_only_players_moves_and_requested_runs(db_session, history):
    player_id, game, run = history
    white, black, other = game("white"), game("black"), game(None)
    a = run(white, [40, 999, 80, 999])
    b = run(black, [999, 120, 999, 60])
    c = run(other, [999]*4)
    run(white, [999]*4)
    candidates = list_practice_candidates(db_session, player_id, [a.id, b.id, c.id])
    assert [(m.game_analysis_id, m.ply) for m in candidates] == [(b.id, 2), (a.id, 3), (b.id, 4), (a.id, 1)]
    assert list_practice_candidates(db_session, player_id, []) == []


@pytest.mark.parametrize("loss, recommendation", [(0, "d2d4"), (None, "d2d4"), (50, None), (50, "e2e4")])
def test_ineligible_moves_are_excluded(db_session, history, loss, recommendation):
    player_id, game, run = history
    saved = run(game("white"), [loss, 999, 0, 999], overrides={0: recommendation})
    assert list_practice_candidates(db_session, player_id, [saved.id]) == []


def test_queue_uses_latest_results_and_one_position_per_game(db_session, history):
    player_id, game, run = history
    white, black = game("white"), game("black")
    run(white, [999, 999, 999, 999])
    latest = run(white, [40, 999, 80, 999], seconds=10)
    second = run(black, [999, 120, 999, 60])
    run(game("white"), [0]*4)
    game("white")  # Unanalyzed games must not inflate the evidence count.
    queue = build_practice_queue(db_session, player_id)
    assert queue.analyzed_game_count == 3
    assert [(p.analysis_id, p.ply, p.color) for p in queue.positions] == [(second.id, 2, "black"), (latest.id, 3, "white")]
    assert queue.positions[0].fen == extract_move_positions(parse_pgn_games(black.pgn)[0])[1]["fen_before"]


def test_equal_losses_have_stable_order(db_session, history):
    player_id, game, run = history
    a = run(game("white"), [50, 0, 50, 0])
    b = run(game("black"), [0, 50, 0, 50])
    assert [(m.game_analysis_id, m.ply) for m in list_practice_candidates(db_session, player_id, [a.id, b.id])] == [(b.id, 2), (b.id, 4), (a.id, 1), (a.id, 3)]


def test_empty_history_returns_empty_queue(db_session, history):
    player_id, _, _ = history
    result = build_practice_queue(db_session, player_id)
    assert result.positions == []
    assert result.analyzed_game_count == 0


@pytest.mark.parametrize("color, ply", [("white", 1), ("black", 2)])
def test_reveal_preserves_old_run_and_checks_player_color(db_session, history, color, ply):
    player_id, make_game, run = history
    game = make_game(color)
    old = run(game, [50]*4)
    run(game, [100]*4, seconds=10)
    move = get_practice_candidate(db_session, player_id, old.id, ply)
    assert move is not None
    assert move.centipawn_loss == 50
    assert move.color == color
    assert get_practice_candidate(db_session, player_id, old.id, 2 if ply == 1 else 1) is None
    assert get_practice_candidate(db_session, player_id, old.id, 999) is None
    stranger = get_or_create_player(db_session, "chess.com", f"stranger_{uuid4().hex}")
    assert get_practice_candidate(db_session, stranger.id, old.id, ply) is None


@pytest.mark.parametrize("loss, recommendation", [(0, "d2d4"), (None, "d2d4"), (50, None), (50, "e2e4")])
def test_reveal_rejects_ineligible_moves(db_session, history, loss, recommendation):
    player_id, game, run = history
    saved = run(game("white"), [loss, 0, 0, 0], overrides={0: recommendation})
    assert get_practice_candidate(db_session, player_id, saved.id, 1) is None


def test_reveal_missing_run(db_session, history):
    player_id, game, run = history
    saved_game = game("white")
    transaction = db_session.begin_nested()
    run_id = run(saved_game, [50]*4).id
    transaction.rollback()
    assert get_practice_candidate(db_session, player_id, run_id, 1) is None
