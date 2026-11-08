from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.models.game import Game
from backend.app.models.game_analysis import GameAnalysis as StoredAnalysis
from backend.app.models.move_analysis import MoveAnalysis as StoredMove
from backend.app.repositories.analyses import (
    create_game_analysis, get_game_analysis_by_id, list_analysis_moves,
)
from backend.app.repositories.games import get_or_create_game
from backend.app.repositories import analyses as analysis_repository
from backend.app.services.engine_analysis import GameAnalysis, MoveAnalysis, PositionAnalysis
from backend.app.services.pgn import extract_move_positions, parse_pgn_games


@pytest.fixture
def analysis_game(db_session):
    token = uuid4().hex
    return get_or_create_game(db_session, {
        "url": f"https://www.chess.com/game/live/{token}",
        "white": {"username": f"white_{token}", "result": "win"},
        "black": {"username": f"black_{token}", "result": "resigned"},
        "time_class": "blitz", "rules": "chess", "end_time": 1234567890,
        "pgn": "1. e4 e5 1-0",
    })


@pytest.fixture
def analysis_result(analysis_game):
    positions = extract_move_positions(parse_pgn_games(analysis_game.pgn)[0])
    scores = [PositionAnalysis("d2d4", 30, None, 12),
              PositionAnalysis("c7c5", -10, None, 13),
              PositionAnalysis("g1f3", 20, None, 12)]
    return GameAnalysis("Test Stockfish", 12, [
        MoveAnalysis(**position, before=scores[i], after=scores[i + 1],
                     centipawn_loss=[40, 30][i])
        for i, position in enumerate(positions)
    ])


def test_analysis_stores_all_fields_and_leaves_input_unchanged(db_session, analysis_game, analysis_result):
    original = deepcopy(analysis_result)
    run_id = create_game_analysis(db_session, analysis_game.id, analysis_result).id
    db_session.expire_all()
    run = db_session.get(StoredAnalysis, run_id)
    assert run.game_id == analysis_game.id
    assert run.engine_name == analysis_result.engine_name
    assert run.requested_depth == 12
    assert run.created_at.utcoffset() is not None
    rows = db_session.scalars(select(StoredMove).where(
        StoredMove.game_analysis_id == run_id,
    ).order_by(StoredMove.ply)).all()
    assert len(rows) == 2
    for row, move in zip(rows, analysis_result.moves):
        for field in ("ply", "color", "uci", "san", "fen_before", "fen_after", "centipawn_loss"):
            assert getattr(row, field) == getattr(move, field)
        for side in ("before", "after"):
            for field in ("best_move", "score_cp", "mate_in", "depth"):
                assert getattr(row, f"{side}_{field}") == getattr(getattr(move, side), field)
    assert analysis_result == original


def test_analysis_preserves_nullable_mate_fields(db_session, analysis_game, analysis_result):
    move = replace(analysis_result.moves[0],
                   before=PositionAnalysis("e2e4", None, -3, None),
                   after=PositionAnalysis(None, None, 0, None), centipawn_loss=None)
    run = create_game_analysis(db_session, analysis_game.id, replace(analysis_result, moves=[move]))
    db_session.expire_all()
    row = db_session.scalars(select(StoredMove).where(StoredMove.game_analysis_id == run.id)).one()
    assert row.before_mate_in == -3
    assert row.after_mate_in == 0
    assert row.before_score_cp is row.after_score_cp is None
    assert row.before_depth is row.after_depth is row.after_best_move is row.centipawn_loss is None


def test_multiple_runs_keep_moves_separate(db_session, analysis_game, analysis_result):
    first = create_game_analysis(db_session, analysis_game.id, analysis_result)
    second = create_game_analysis(db_session, analysis_game.id, analysis_result)
    assert first.id != second.id
    for run in (first, second):
        assert len(db_session.scalars(select(StoredMove).where(StoredMove.game_analysis_id == run.id)).all()) == 2


def test_empty_analysis_inserts_nothing(db_session, analysis_game, analysis_result):
    with pytest.raises(ValueError, match="at least one move"):
        create_game_analysis(db_session, analysis_game.id, replace(analysis_result, moves=[]))
    assert db_session.scalars(select(StoredAnalysis).where(StoredAnalysis.game_id == analysis_game.id)).all() == []


def test_analysis_repository_does_not_commit(db_session, analysis_game, analysis_result, monkeypatch):
    def fail_commit():
        pytest.fail("The caller owns the transaction")
    monkeypatch.setattr(db_session, "commit", fail_commit)
    assert create_game_analysis(db_session, analysis_game.id, analysis_result).id is not None


def test_caller_can_roll_back_entire_analysis(db_session, analysis_game, analysis_result):
    transaction = db_session.begin_nested()
    run_id = create_game_analysis(db_session, analysis_game.id, analysis_result).id
    transaction.rollback()
    assert db_session.get(StoredAnalysis, run_id) is None
    assert db_session.scalars(select(StoredMove).where(StoredMove.game_analysis_id == run_id)).all() == []


@pytest.mark.parametrize("field, value, constraint", [
    ("ply", 0, "ck_move_analyses_positive_ply"),
    ("color", "other", "ck_move_analyses_valid_color"),
    ("centipawn_loss", -1, "ck_move_analyses_nonnegative_centipawn_loss"),
    ("ply", 1, "uq_move_analyses_run_ply"),
])
def test_invalid_move_rolls_back_new_run_but_preserves_existing(
    db_session, analysis_game, analysis_result, field, value, constraint,
):
    existing = create_game_analysis(db_session, analysis_game.id, analysis_result)
    bad_move = replace(analysis_result.moves[1], **{field: value})
    invalid = replace(analysis_result, moves=[analysis_result.moves[0], bad_move])
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            create_game_analysis(db_session, analysis_game.id, invalid)
    assert error.value.orig.diag.constraint_name == constraint
    assert db_session.scalars(select(StoredAnalysis.id).where(StoredAnalysis.game_id == analysis_game.id)).all() == [existing.id]
    assert len(db_session.scalars(select(StoredMove).where(StoredMove.game_analysis_id == existing.id)).all()) == 2


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("cp, mate", [(None, None), (20, 3)])
def test_database_requires_exactly_one_score_type(db_session, analysis_game, analysis_result, side, cp, mate):
    move = replace(analysis_result.moves[0], **{side: PositionAnalysis(None, cp, mate, 12)})
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            create_game_analysis(db_session, analysis_game.id, replace(analysis_result, moves=[move]))
    assert error.value.orig.diag.constraint_name == f"ck_move_analyses_one_{side}_score"


def test_database_rejects_nonpositive_depth(db_session, analysis_game, analysis_result):
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            create_game_analysis(db_session, analysis_game.id, replace(analysis_result, requested_depth=0))
    assert error.value.orig.diag.constraint_name == "ck_game_analyses_positive_requested_depth"


def test_database_rejects_missing_game(db_session, analysis_game, analysis_result):
    game_id = analysis_game.id
    db_session.delete(analysis_game)
    db_session.flush()
    assert db_session.get(Game, game_id) is None
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            create_game_analysis(db_session, game_id, analysis_result)
    assert error.value.orig.diag.constraint_name == "fk_game_analyses_game_id_games"


def test_retrieval_orders_moves_and_excludes_other_runs(db_session, analysis_game, analysis_result):
    first = create_game_analysis(db_session, analysis_game.id, replace(
        analysis_result, moves=list(reversed(analysis_result.moves)),
    ))
    second = create_game_analysis(db_session, analysis_game.id, analysis_result)
    first_id, second_id = first.id, second.id
    db_session.expire_all()
    assert get_game_analysis_by_id(db_session, first_id).engine_name == analysis_result.engine_name
    rows = list_analysis_moves(db_session, first_id)
    assert [row.ply for row in rows] == [1, 2]
    assert all(row.game_analysis_id == first_id for row in rows)
    assert first_id != second_id


def test_retrieval_missing_run_returns_none_and_empty_list(db_session, analysis_game, analysis_result):
    transaction = db_session.begin_nested()
    run_id = create_game_analysis(db_session, analysis_game.id, analysis_result).id
    transaction.rollback()
    assert get_game_analysis_by_id(db_session, run_id) is None
    assert list_analysis_moves(db_session, run_id) == []


def test_list_runs_filters_game_and_orders_before_pagination(db_session, analysis_game, analysis_result):
    other_game = get_or_create_game(db_session, {
        "url": f"https://www.chess.com/game/live/{uuid4().hex}",
        "white": {"username": f"white_{uuid4().hex}", "result": "win"},
        "black": {"username": f"black_{uuid4().hex}", "result": "resigned"},
        "rules": "chess", "time_class": "blitz", "end_time": 1234567890,
        "pgn": "1. e4 e5 1-0",
    })
    base = datetime(2026, 1, 1, tzinfo=UTC)
    runs = []
    # Insertion order differs from time order; the last two timestamps tie.
    for seconds in [30, 0, 20, 20]:
        run = create_game_analysis(db_session, analysis_game.id, analysis_result)
        run.created_at = base + timedelta(seconds=seconds)
        runs.append(run)
    unrelated = create_game_analysis(db_session, other_game.id, analysis_result)
    unrelated.created_at = base + timedelta(seconds=40)
    db_session.flush()
    expected = [runs[i].id for i in [0, 3, 2, 1]]
    assert [r.id for r in analysis_repository.list_game_analyses(db_session, analysis_game.id)] == expected
    for offset in [0, 2, 3, 4, 10]:
        result = analysis_repository.list_game_analyses(db_session, analysis_game.id, limit=2, offset=offset)
        assert [r.id for r in result] == expected[offset:offset + 2]


def test_list_runs_empty_and_default_limit(db_session, analysis_game, analysis_result):
    assert analysis_repository.list_game_analyses(db_session, analysis_game.id) == []
    ids = [create_game_analysis(db_session, analysis_game.id, analysis_result).id for _ in range(21)]
    # PostgreSQL now() is constant in this transaction, exercising the ID tie-break.
    result = analysis_repository.list_game_analyses(db_session, analysis_game.id)
    assert [r.id for r in result] == list(reversed(ids))[:20]
