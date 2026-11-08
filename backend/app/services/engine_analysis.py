from dataclasses import dataclass
from backend.app.services.pgn import parse_pgn_games

import chess
import chess.engine

from collections.abc import Iterable
from typing import Protocol


@dataclass(frozen=True)
class PositionAnalysis:
    best_move: str | None
    score_cp: int | None
    mate_in: int | None
    depth: int | None

@dataclass(frozen=True)
class MoveAnalysis:
    ply: int
    color: str
    uci: str
    san: str
    fen_before: str
    fen_after: str
    before: PositionAnalysis
    after: PositionAnalysis
    centipawn_loss: int | None


@dataclass(frozen=True)
class PlayerAnalysisSummary:
    color: str
    total_moves: int
    scored_moves: int
    unscored_moves: int
    average_centipawn_loss: float | None


@dataclass(frozen=True)
class GameAnalysis:
    engine_name: str
    requested_depth: int
    moves: list[MoveAnalysis]


def _analyze_board(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    *,
    depth: int,
) -> PositionAnalysis:
    info = engine.analyse(
        board,
        chess.engine.Limit(depth=depth),
    )

    score = info["score"].white()
    principal_variation = info.get("pv", [])

    return PositionAnalysis(
        best_move=(
            principal_variation[0].uci()
            if principal_variation
            else None
        ),
        score_cp=score.score(),
        mate_in=score.mate(),
        depth=info.get("depth"),
    )


def calculate_centipawn_loss(
    before: PositionAnalysis,
    after: PositionAnalysis,
    *,
    color: str,
) -> int | None:
    if color not in {"white", "black"}:
        raise ValueError("color must be 'white' or 'black'")

    if before.score_cp is None or after.score_cp is None:
        return None

    if color == "white":
        loss = before.score_cp - after.score_cp
    else:
        loss = after.score_cp - before.score_cp

    return max(0, loss)


def analyze_position(
    fen: str,
    *,
    engine_path: str,
    depth: int = 12,
) -> PositionAnalysis:
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError("depth must be a positive integer")

    board = chess.Board(fen)

    if not board.is_valid():
        raise ValueError("FEN must describe a valid standard chess position")

    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        return _analyze_board(engine, board, depth=depth)


def analyze_game(
    pgn_text: str,
    *,
    engine_path: str,
    depth: int = 12,
) -> GameAnalysis:
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError("depth must be a positive integer")

    games = parse_pgn_games(pgn_text)

    if len(games) != 1:
        raise ValueError("PGN must contain exactly one playable game")

    game = games[0]
    board = game.board()

    if board.uci_variant != "chess" or board.chess960:
        raise ValueError("Only standard chess is supported")

    if not board.is_valid():
        raise ValueError("PGN must start from a valid chess position")

    results = []

    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        engine_name = engine.id["name"]
        before = _analyze_board(engine, board, depth=depth)

        for ply, move in enumerate(game.mainline_moves(), start=1):
            color = "white" if board.turn == chess.WHITE else "black"
            fen_before = board.fen()
            san = board.san(move)

            board.push(move)

            after = _analyze_board(engine, board, depth=depth)

            results.append(
                MoveAnalysis(
                    ply=ply,
                    color=color,
                    uci=move.uci(),
                    san=san,
                    fen_before=fen_before,
                    fen_after=board.fen(),
                    before=before,
                    after=after,
                    centipawn_loss=calculate_centipawn_loss(before, after, color = color)
                )
            )

            before = after

    return GameAnalysis(engine_name = engine_name, requested_depth= depth, moves = results)



class SummarizableMove(Protocol):
    @property
    def color(self) -> str: ...

    @property
    def centipawn_loss(self) -> int | None: ...



def summarize_player_analysis(
    moves: Iterable[SummarizableMove],
    *,
    color: str,
) -> PlayerAnalysisSummary:
    if color not in {"white", "black"}:
        raise ValueError("color must be 'white' or 'black'")

    player_moves = [move for move in moves if move.color == color]

    losses = [
        move.centipawn_loss
        for move in player_moves
        if move.centipawn_loss is not None
    ]

    return PlayerAnalysisSummary(
        color=color,
        total_moves=len(player_moves),
        scored_moves=len(losses),
        unscored_moves=len(player_moves) - len(losses),
        average_centipawn_loss=(
            sum(losses) / len(losses)
            if losses
            else None
        ),
    )
