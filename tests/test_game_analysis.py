from types import SimpleNamespace

import chess
import chess.engine
import pytest

from backend.app.services import engine_analysis


@pytest.fixture
def game_engine(monkeypatch):
    state = SimpleNamespace(paths=[], calls=[], exits=[], fail_at=None)

    class Engine:
        id = {"name": "Stockfish Test Version"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            state.exits.append(exc)
            return False

        def analyse(self, board, limit):
            # Snapshot: the service mutates the same board for subsequent moves.
            state.calls.append((board.copy(), limit.depth))
            if len(state.calls) == state.fail_at:
                raise chess.engine.EngineError("Search failed")
            score = chess.engine.Mate(0) if board.is_checkmate() else chess.engine.Cp(len(state.calls) * 10)
            moves = list(board.legal_moves)
            return {
                "score": chess.engine.PovScore(score, board.turn),
                "pv": moves[:1],
                "depth": limit.depth,
            }

    def launch(path):
        state.paths.append(path)
        return Engine()

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", launch)
    return state


def test_game_reuses_one_engine_and_evaluates_each_position_once(game_engine):
    analysis = engine_analysis.analyze_game("1. e4 e5 *", engine_path="test-engine", depth=8)
    assert isinstance(analysis, engine_analysis.GameAnalysis)
    assert analysis.engine_name == "Stockfish Test Version"
    assert analysis.requested_depth == 8
    results = analysis.moves
    assert game_engine.paths == ["test-engine"]
    assert len(game_engine.calls) == 3
    assert [depth for _, depth in game_engine.calls] == [8, 8, 8]
    assert [(r.ply, r.color, r.uci, r.san) for r in results] == [
        (1, "white", "e2e4", "e4"), (2, "black", "e7e5", "e5"),
    ]
    assert results[0].fen_before == chess.STARTING_FEN
    assert results[0].fen_after == results[1].fen_before
    assert results[1].fen_after == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    assert results[0].before.score_cp == 10
    assert results[0].after.score_cp == -20
    assert results[1].after.score_cp == 30
    # White loses 10 - (-20); Black loses 30 - (-20).
    assert [result.centipawn_loss for result in results] == [30, 50]
    assert results[1].before is results[0].after
    for index, result in enumerate(results):
        before_board = game_engine.calls[index][0]
        after_board = game_engine.calls[index + 1][0]
        assert result.fen_before == before_board.fen()
        assert result.fen_after == after_board.fen()
        assert chess.Move.from_uci(result.before.best_move) in before_board.legal_moves
        assert chess.Move.from_uci(result.after.best_move) in after_board.legal_moves
    assert game_engine.exits == [None]


def test_game_uses_default_depth(game_engine):
    analysis = engine_analysis.analyze_game("1. e4 *", engine_path="stockfish")
    assert analysis.requested_depth == 12
    assert [depth for _, depth in game_engine.calls] == [12, 12]


def test_game_respects_black_to_move_starting_fen(game_engine):
    pgn = '[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/K7 b - - 0 12"]\n\n12... Kg8 *'
    results = engine_analysis.analyze_game(pgn, engine_path="stockfish").moves
    assert len(results) == 1
    assert (results[0].ply, results[0].color, results[0].san) == (1, "black", "Kg8")
    assert results[0].fen_after == "6k1/8/8/8/8/8/8/K7 w - - 1 13"


def test_game_handles_checkmate_on_last_move(game_engine):
    results = engine_analysis.analyze_game("1. f3 e5 2. g4 Qh4# 0-1", engine_path="stockfish").moves
    assert len(results) == 4
    assert len(game_engine.calls) == 5
    assert results[-1].san == "Qh4#"
    assert results[-1].after.best_move is None
    assert results[-1].after.score_cp is None
    assert results[-1].after.mate_in == 0
    assert results[-1].centipawn_loss is None
    assert game_engine.exits == [None]


@pytest.mark.parametrize("depth", [0, -1, True, False, 1.5, "12", None])
def test_game_rejects_invalid_depth_before_launch(game_engine, depth):
    with pytest.raises(ValueError, match="positive integer"):
        engine_analysis.analyze_game("1. e4 *", engine_path="stockfish", depth=depth)
    assert game_engine.paths == []


@pytest.mark.parametrize("pgn", [
    "", " \n\t", None, 123,
    '[Result "*"]\n\n*',
    '1. e4 *\n\n[Result "*"]\n\n1. d4 *',
    "1. e4 e5 2. Bh6 *",
    '[Variant "Atomic"]\n\n1. e4 *',
    '[Variant "Chess960"]\n\n1. e4 *',
    '[SetUp "1"]\n[FEN "8/8/8/8/8/8/P7/7k w - - 0 1"]\n\n1. a3 *',
])
def test_game_rejects_invalid_or_unsupported_pgn_before_launch(game_engine, pgn):
    with pytest.raises(ValueError):
        engine_analysis.analyze_game(pgn, engine_path="stockfish")
    assert game_engine.paths == []


@pytest.mark.parametrize("fail_at", [1, 3])
def test_game_closes_engine_and_propagates_search_failure(game_engine, fail_at):
    game_engine.fail_at = fail_at
    with pytest.raises(chess.engine.EngineError, match="Search failed") as error:
        engine_analysis.analyze_game("1. e4 e5 *", engine_path="stockfish")
    assert len(game_engine.calls) == fail_at
    assert game_engine.exits == [error.value]


def test_game_propagates_missing_executable(monkeypatch):
    def launch(path):
        raise FileNotFoundError("Missing engine")

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", launch)
    with pytest.raises(FileNotFoundError, match="Missing engine"):
        engine_analysis.analyze_game("1. e4 *", engine_path="missing")
