from types import SimpleNamespace

import chess
import chess.engine
import pytest

from backend.app.services.engine_analysis import PositionAnalysis, analyze_position


@pytest.fixture
def fake_engine(monkeypatch):
    state = SimpleNamespace(
        paths=[], calls=[], exits=[], error=None,
        info={
            "score": chess.engine.PovScore(chess.engine.Cp(31), chess.WHITE),
            "pv": [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")],
            "depth": 10,
        },
    )

    class Engine:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            state.exits.append(exc)
            return False

        def analyse(self, board, limit):
            state.calls.append((board, limit))
            if state.error is not None:
                raise state.error
            return state.info

    def launch(path):
        state.paths.append(path)
        return Engine()

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", launch)
    return state


def test_position_analysis_passes_settings_and_returns_first_pv_move(fake_engine):
    result = analyze_position(chess.STARTING_FEN, engine_path="test-stockfish", depth=10)
    assert result == PositionAnalysis("e2e4", 31, None, 10)
    assert fake_engine.paths == ["test-stockfish"]
    assert len(fake_engine.calls) == 1
    board, limit = fake_engine.calls[0]
    assert board.fen() == chess.STARTING_FEN
    assert limit.depth == 10
    assert fake_engine.exits == [None]


def test_default_search_depth(fake_engine):
    analyze_position(chess.STARTING_FEN, engine_path="stockfish")
    assert fake_engine.calls[0][1].depth == 12


@pytest.mark.parametrize("score, pov, expected", [
    (50, chess.WHITE, 50),
    (-50, chess.WHITE, -50),
    (50, chess.BLACK, -50),
    (-50, chess.BLACK, 50),
    (0, chess.BLACK, 0),
])
def test_centipawn_scores_are_white_relative(fake_engine, score, pov, expected):
    fake_engine.info["score"] = chess.engine.PovScore(chess.engine.Cp(score), pov)
    result = analyze_position(chess.STARTING_FEN, engine_path="stockfish")
    assert result.score_cp == expected
    assert result.mate_in is None


@pytest.mark.parametrize("distance, pov, expected", [
    (3, chess.WHITE, 3), (-3, chess.WHITE, -3),
    (3, chess.BLACK, -3), (-3, chess.BLACK, 3),
])
def test_mate_scores_are_separate_and_white_relative(fake_engine, distance, pov, expected):
    fake_engine.info["score"] = chess.engine.PovScore(chess.engine.Mate(distance), pov)
    result = analyze_position(chess.STARTING_FEN, engine_path="stockfish")
    assert result.score_cp is None
    assert result.mate_in == expected


@pytest.mark.parametrize("pv", [None, []])
def test_terminal_position_can_have_no_pv_or_depth(fake_engine, pv):
    # Black is checkmated. No legal recommendation is available.
    fen = "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"
    fake_engine.info = {"score": chess.engine.PovScore(chess.engine.Mate(0), chess.BLACK)}
    if pv is not None:
        fake_engine.info["pv"] = pv
    result = analyze_position(fen, engine_path="stockfish")
    assert result == PositionAnalysis(None, None, 0, None)
    assert fake_engine.calls[0][0].is_checkmate()


@pytest.mark.parametrize("depth", [0, -1, True, False, 1.5, "10", None])
def test_invalid_depth_rejected_before_engine_launch(fake_engine, depth):
    with pytest.raises(ValueError, match="depth must be a positive integer"):
        analyze_position(chess.STARTING_FEN, engine_path="stockfish", depth=depth)
    assert fake_engine.paths == []


@pytest.mark.parametrize("fen", ["", "not a FEN", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_fen_rejected_before_engine_launch(fake_engine, fen):
    with pytest.raises(ValueError):
        analyze_position(fen, engine_path="stockfish")
    assert fake_engine.paths == []


def test_engine_context_exits_when_analysis_fails(fake_engine):
    error = chess.engine.EngineError("Analysis failed")
    fake_engine.error = error
    with pytest.raises(chess.engine.EngineError) as caught:
        analyze_position(chess.STARTING_FEN, engine_path="stockfish")
    assert caught.value is error
    assert fake_engine.exits == [error]


def test_launch_failure_propagates(monkeypatch):
    def fail_launch(path):
        raise FileNotFoundError("Stockfish executable missing")

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", fail_launch)
    with pytest.raises(FileNotFoundError, match="executable missing"):
        analyze_position(chess.STARTING_FEN, engine_path="missing-stockfish")
