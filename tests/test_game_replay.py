import pytest

from backend.app.services.game_replay import GameReplayError, build_game_moves


def test_replay_returns_exact_positions():
    moves = build_game_moves("1. e4 e5 *")
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    after_white = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    after_black = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    assert moves == [
        dict(ply=1, color="white", uci="e2e4", san="e4", fen_before=start, fen_after=after_white),
        dict(ply=2, color="black", uci="e7e5", san="e5", fen_before=after_white, fen_after=after_black),
    ]


@pytest.mark.parametrize("text", ["", " \n\t", None, 123])
def test_replay_wraps_invalid_input(text):
    with pytest.raises(GameReplayError, match="could not be processed"):
        build_game_moves(text)


@pytest.mark.parametrize("text", [
    '[Result "*"]\n\n*',
    '[Result "*"]\n\n1. e4 *\n\n[Result "*"]\n\n1. d4 *',
])
def test_replay_requires_one_playable_game(text):
    with pytest.raises(GameReplayError, match="exactly one playable game"):
        build_game_moves(text)


def test_replay_rejects_nonstandard_variant():
    with pytest.raises(GameReplayError, match="Only standard chess"):
        build_game_moves('[Variant "Atomic"]\n\n1. e4 *')


def test_replay_respects_custom_starting_position():
    text = '[SetUp "1"]\n[FEN "7k/8/8/8/8/8/8/K7 b - - 0 12"]\n\n12... Kg8 *'
    moves = build_game_moves(text)
    assert moves == [dict(
        ply=1, color="black", uci="h8g8", san="Kg8",
        fen_before="7k/8/8/8/8/8/8/K7 b - - 0 12",
        fen_after="6k1/8/8/8/8/8/8/K7 w - - 1 13",
    )]


def test_replay_rejects_illegal_move_after_valid_moves():
    # Bh6 is blocked by White's g2 pawn. The valid opening must not be
    # returned as a successful, truncated replay.
    pgn_text = '[Result "*"]\n\n1. e4 e5 2. Bh6 *'

    with pytest.raises(
        GameReplayError, match="Saved PGN could not be processed"
    ) as error:
        build_game_moves(pgn_text)

    assert isinstance(error.value.__cause__, ValueError)
    assert str(error.value.__cause__) == "PGN contains parsing errors"
