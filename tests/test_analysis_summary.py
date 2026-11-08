from copy import deepcopy

import pytest

from backend.app.services import engine_analysis


def make_move(color, loss):
    """Build a move record; summary tests depend only on color and loss."""
    before = engine_analysis.PositionAnalysis(None, 0, None, 12)
    after = engine_analysis.PositionAnalysis(
        None,
        None if loss is None else (-loss if color == "white" else loss),
        3 if loss is None else None,
        12,
    )
    return engine_analysis.MoveAnalysis(
        ply=1, color=color, uci="e2e4" if color == "white" else "e7e5",
        san="e4" if color == "white" else "e5",
        fen_before="", fen_after="", before=before, after=after,
        centipawn_loss=loss,
    )


@pytest.mark.parametrize("color", ["white", "black"])
def test_summary_filters_color_and_includes_zero_in_average(color):
    opponent = "black" if color == "white" else "white"
    moves = [make_move(color, 0), make_move(opponent, 900),
             make_move(color, 60), make_move(color, None)]
    original = deepcopy(moves)

    result = engine_analysis.summarize_player_analysis(moves, color=color)

    assert result == engine_analysis.PlayerAnalysisSummary(
        color=color, total_moves=3, scored_moves=2, unscored_moves=1,
        average_centipawn_loss=30.0,
    )
    assert moves == original


@pytest.mark.parametrize("losses, expected", [
    ([], None),
    ([None, None], None),
    ([0, 0], 0.0),
    ([75], 75.0),
    ([0, 0, 1], 1 / 3),
])
def test_summary_handles_empty_unscored_zero_and_fractional_results(losses, expected):
    moves = [make_move("white", loss) for loss in losses]
    result = engine_analysis.summarize_player_analysis(moves, color="white")

    assert result.total_moves == len(losses)
    assert result.unscored_moves == losses.count(None)
    assert result.scored_moves == len(losses) - losses.count(None)
    if expected is None:
        assert result.average_centipawn_loss is None
    else:
        assert result.average_centipawn_loss == pytest.approx(expected)


def test_summary_returns_no_data_when_only_opponent_has_moves():
    result = engine_analysis.summarize_player_analysis(
        [make_move("black", 50)], color="white",
    )
    assert result == engine_analysis.PlayerAnalysisSummary(
        color="white", total_moves=0, scored_moves=0, unscored_moves=0,
        average_centipawn_loss=None,
    )


@pytest.mark.parametrize("color", ["White", "BLACK", "", "green", None])
def test_summary_rejects_invalid_color_even_with_no_moves(color):
    with pytest.raises(ValueError, match="color must be 'white' or 'black'"):
        engine_analysis.summarize_player_analysis([], color=color)
