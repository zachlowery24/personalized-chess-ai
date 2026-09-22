import io

import chess.pgn


def parse_pgn_games(pgn_text: str) -> list[chess.pgn.Game]:
    if not isinstance(pgn_text, str) or not pgn_text.strip():
        raise ValueError("PGN must be a nonempty string")

    stream = io.StringIO(pgn_text)
    games = []

    while True:
        game = chess.pgn.read_game(stream)

        if game is None:
            break

        if game.errors:
            raise ValueError("PGN contains parsing errors") from game.errors[0]

        if not game.variations:
            continue

        games.append(game)

    return games


def extract_move_positions(game: chess.pgn.Game) -> list[dict]:
    board = game.board()
    positions = []

    for ply, move in enumerate(game.mainline_moves(), start = 1):
        fen_before = board.fen()
        color = "white" if board.turn == chess.WHITE else "black"
        san = board.san(move)
        board.push(move)
        fen_after = board.fen()

        positions.append({
            "ply": ply,
            "color": color,
            "uci": move.uci(),
            "san": san,
            "fen_before": fen_before,
            "fen_after": fen_after,
        })

    return positions