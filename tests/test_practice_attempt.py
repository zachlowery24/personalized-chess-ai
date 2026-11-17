from types import SimpleNamespace

import chess
import chess.engine
import pytest

from backend.app.services.practice_attempt import evaluate_practice_attempt


def info(cp=30, moves=("e2e4", "e7e5"), *, mate=None, pov=chess.WHITE):
    score = chess.engine.Cp(cp) if mate is None else chess.engine.Mate(mate)
    return {
        "score": chess.engine.PovScore(score, pov),
        "pv": [chess.Move.from_uci(move) for move in moves],
        "depth": 12,
    }


@pytest.fixture
def engine(monkeypatch):
    state = SimpleNamespace(
        responses=[info(), info(10, ("d2d4", "d7d5"))],
        paths=[], calls=[], exits=[], error=None,
    )

    class FakeEngine:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            state.exits.append(exc)

        def analyse(self, board, limit, *, root_moves):
            state.calls.append((board.fen(), limit.depth, root_moves))
            if state.error:
                raise state.error
            return state.responses.pop(0)

    def launch(path):
        state.paths.append(path)
        return FakeEngine()

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", launch)
    return state


def evaluate(move="d2d4", fen=chess.STARTING_FEN, **kwargs):
    return evaluate_practice_attempt(fen, move, engine_path="fake-stockfish", **kwargs)


def test_alternative_search_uses_same_position_and_forces_attempt(engine):
    result = evaluate(depth=10)
    assert engine.paths == ["fake-stockfish"]
    assert engine.calls == [
        (chess.STARTING_FEN, 10, None),
        (chess.STARTING_FEN, 10, [chess.Move.from_uci("d2d4")]),
    ]
    assert result.attempted_san == "d4"
    assert result.recommended_san == "e4"
    assert result.attempted_move == "d2d4"
    assert result.recommended_move == "e2e4"
    assert result.centipawn_loss == 20
    assert result.attempted_line.moves == ["d2d4", "d7d5"]
    assert result.recommended_line.moves == ["e2e4", "e7e5"]
    assert engine.exits == [None]


def test_matching_recommendation_reuses_search(engine):
    result = evaluate("e2e4")
    assert len(engine.calls) == 1
    assert engine.calls[0][1] == 12
    assert result.attempted_line is result.recommended_line
    assert result.centipawn_loss == 0


@pytest.mark.parametrize("attempt_score, expected", [(30, 0), (50, 0), (-100, 130)])
def test_alternatives_can_be_equal_better_or_worse(engine, attempt_score, expected):
    engine.responses[1] = info(attempt_score, ("d2d4",))
    assert evaluate().centipawn_loss == expected


def test_black_loss_and_scores_use_correct_perspective(engine):
    board = chess.Board()
    board.push_uci("e2e4")
    engine.responses = [
        info(-20, ("e7e5",), pov=chess.BLACK),
        info(-100, ("d7d5",), pov=chess.BLACK),
    ]
    result = evaluate("d7d5", board.fen())
    assert result.recommended_line.evaluation.score_cp == 20
    assert result.attempted_line.evaluation.score_cp == 100
    assert result.centipawn_loss == 80


@pytest.mark.parametrize("first_mate, second_mate", [(3, None), (None, -2), (3, 4)])
def test_mate_scores_remain_separate(engine, first_mate, second_mate):
    engine.responses = [
        info(mate=first_mate),
        info(moves=("d2d4",), mate=second_mate),
    ]
    result = evaluate()
    assert result.centipawn_loss is None
    assert result.recommended_line.evaluation.mate_in == first_mate
    assert result.attempted_line.evaluation.mate_in == second_mate


def test_continuation_is_limited_to_six_moves(engine):
    moves = ("e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4")
    engine.responses = [info(moves=moves)]
    assert evaluate("e2e4").recommended_line.moves == list(moves[:6])


@pytest.mark.parametrize("depth", [0, 21, -1, True, False, 1.5, "12", None])
def test_invalid_depth_does_not_launch_engine(engine, depth):
    with pytest.raises(ValueError, match="depth must"):
        evaluate(depth=depth)
    assert engine.paths == []


@pytest.mark.parametrize("move", ["e2e5", "e7e5", "nonsense", "0000"])
def test_illegal_malformed_and_null_moves_rejected(engine, move):
    with pytest.raises(ValueError):
        evaluate(move)
    assert engine.paths == []


@pytest.mark.parametrize("fen", ["not fen", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_position_rejected(engine, fen):
    with pytest.raises(ValueError):
        evaluate(fen=fen)
    assert engine.paths == []


def test_promotion_is_preserved_in_uci_and_san(engine):
    fen = "7k/P7/8/8/8/8/8/7K w - - 0 1"
    engine.responses = [info(moves=("a7a8q",))]
    result = evaluate("a7a8q", fen)
    assert result.attempted_move == "a7a8q"
    assert result.attempted_san == "a8=Q+"


def test_missing_recommendation_raises_and_closes_engine(engine):
    engine.responses = [info(moves=())]
    with pytest.raises(chess.engine.EngineError, match="recommended move"):
        evaluate()
    assert len(engine.exits) == 1
    assert isinstance(engine.exits[0], chess.engine.EngineError)


def test_search_error_propagates_and_closes_engine(engine):
    engine.error = chess.engine.EngineError("search failed")
    with pytest.raises(chess.engine.EngineError, match="search failed"):
        evaluate()
    assert engine.exits == [engine.error]
