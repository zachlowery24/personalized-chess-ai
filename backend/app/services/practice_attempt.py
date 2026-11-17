from dataclasses import dataclass

import chess
import chess.engine

from backend.app.services.engine_analysis import (
    PositionAnalysis,
    calculate_centipawn_loss,
)


@dataclass(frozen=True)
class PracticeLine:
    evaluation: PositionAnalysis
    moves: list[str]


@dataclass(frozen=True)
class PracticeAttempt:
    attempted_move: str
    attempted_san: str
    recommended_move: str
    recommended_san: str
    recommended_line: PracticeLine
    attempted_line: PracticeLine
    centipawn_loss: int | None


def _evaluate_line(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    *,
    depth: int,
    root_move: chess.Move | None = None,
) -> PracticeLine:
    info = engine.analyse(
        board,
        chess.engine.Limit(depth=depth),
        root_moves=[root_move] if root_move is not None else None,
    )

    score = info["score"].white()
    variation = info.get("pv", [])

    return PracticeLine(
        evaluation=PositionAnalysis(
            best_move=variation[0].uci() if variation else None,
            score_cp=score.score(),
            mate_in=score.mate(),
            depth=info.get("depth"),
        ),
        moves=[move.uci() for move in variation[:6]],
    )


def evaluate_practice_attempt(
    fen: str,
    attempted_move: str,
    *,
    engine_path: str,
    depth: int = 12,
) -> PracticeAttempt:
    if (
        not isinstance(depth, int)
        or isinstance(depth, bool)
        or not 1 <= depth <= 20
    ):
        raise ValueError("depth must be an integer between 1 and 20")

    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError("FEN must describe a valid standard chess position")

    # parse_uci checks both the notation and legality in this position.
    move = board.parse_uci(attempted_move)

    if not move:
        raise ValueError("A move must be played")

    color = "white" if board.turn == chess.WHITE else "black"

    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        recommended = _evaluate_line(engine, board, depth=depth)

        best_uci = recommended.evaluation.best_move
        if best_uci is None:
            raise chess.engine.EngineError(
                "Engine did not return a recommended move"
            )

        best_move = board.parse_uci(best_uci)

        attempted = (
            recommended
            if move == best_move
            else _evaluate_line(
                engine,
                board,
                depth=depth,
                root_move=move,
            )
        )

    return PracticeAttempt(
        attempted_move=move.uci(),
        attempted_san=board.san(move),
        recommended_move=best_move.uci(),
        recommended_san=board.san(best_move),
        recommended_line=recommended,
        attempted_line=attempted,
        centipawn_loss=calculate_centipawn_loss(
            recommended.evaluation,
            attempted.evaluation,
            color=color,
        ),
    )
