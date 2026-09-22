import pytest
import chess

from backend.app.services.pgn import parse_pgn_games, extract_move_positions


def test_parses_moves():
    games = parse_pgn_games("1. e4 e5 2. Nf3 Nc6 *")

    assert len(games) == 1
    assert [move.uci() for move in games[0].mainline_moves()] == [
        "e2e4",
        "e7e5",
        "g1f3",
        "b8c6",
    ]

def test_skips_game_without_moves():
    pgn_text = '[Event "Empty game"]\n\n*'

    assert parse_pgn_games(pgn_text) == []


def test_parses_multiple_games():
    pgn_text = """
[Event "First game"]

1. e4 e5 *

[Event "Second game"]

1. d4 d5 *
"""
    games = parse_pgn_games(pgn_text)

    assert len(games) == 2
    assert games[0].headers["Event"] == "First game"
    assert games[1].headers["Event"] == "Second game"

    assert [move.uci() for move in games[0].mainline_moves()] == [
        "e2e4", "e7e5",
    ]
    assert [move.uci() for move in games[1].mainline_moves()] == [
        "d2d4", "d7d5",
    ]

def test_skips_empty_game_and_continues_parsing():
    pgn_text = """
[Event "First"]

1. e4 e5 *

[Event "Empty"]

*

[Event "Last"]

1. d4 d5 *
"""
    games = parse_pgn_games(pgn_text)

    assert [game.headers["Event"] for game in games] == ["First", "Last"]

@pytest.mark.parametrize("pgn_text", ["", " \n\t", None, 123])
def test_rejects_invalid_input(pgn_text):
    with pytest.raises(ValueError, match="PGN must be a nonempty string"):
        parse_pgn_games(pgn_text)



def test_rejects_illegal_move():
    with pytest.raises(ValueError, match="PGN contains parsing errors") as error:
        parse_pgn_games("1. e4 e5 2. Bh6 *")

    assert error.value.__cause__ is not None

def test_replays_moves_to_final_position():
    game = parse_pgn_games("1. e4 e5 2. Nf3 Nc6 *")[0]
    board = game.board()

    for move in game.mainline_moves():
        board.push(move)

    assert board.fullmove_number == 3
    assert board.turn == chess.WHITE
    assert board.piece_at(chess.F3) == chess.Piece(chess.KNIGHT, chess.WHITE)
    assert board.piece_at(chess.C6) == chess.Piece(chess.KNIGHT, chess.BLACK)


def test_extracts_move_positions():
    game = parse_pgn_games("1. e4 e5 *")[0]

    positions = extract_move_positions(game)

    assert len(positions) == 2

    first = positions[0]
    assert first["ply"] == 1
    assert first["color"] == "white"
    assert first["uci"] == "e2e4"
    assert first["san"] == "e4"
    assert first["fen_before"] == chess.STARTING_FEN

    after_white = chess.Board(first["fen_after"])
    assert after_white.piece_at(chess.E2) is None
    assert after_white.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert after_white.turn == chess.BLACK

    second = positions[1]
    assert second["ply"] == 2
    assert second["color"] == "black"
    assert second["uci"] == "e7e5"
    assert second["san"] == "e5"
    assert second["fen_before"] == first["fen_after"]

    after_black = chess.Board(second["fen_after"])
    assert after_black.piece_at(chess.E7) is None
    assert after_black.piece_at(chess.E5) == chess.Piece(chess.PAWN, chess.BLACK)
    assert after_black.turn == chess.WHITE



def test_extracts_castling_from_custom_position():
    pgn_text = """
[SetUp "1"]
[FEN "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"]

1. O-O *
"""
    game = parse_pgn_games(pgn_text)[0]

    positions = extract_move_positions(game)

    assert len(positions) == 1
    move = positions[0]
    assert move["fen_before"] == game.headers["FEN"]
    assert move["san"] == "O-O"
    assert move["uci"] == "e1g1"

    board = chess.Board(move["fen_after"])
    assert board.piece_at(chess.G1) == chess.Piece(chess.KING, chess.WHITE)
    assert board.piece_at(chess.F1) == chess.Piece(chess.ROOK, chess.WHITE)
    assert board.piece_at(chess.E1) is None
    assert board.piece_at(chess.H1) is None
    assert not board.has_kingside_castling_rights(chess.WHITE)
    assert not board.has_queenside_castling_rights(chess.WHITE)