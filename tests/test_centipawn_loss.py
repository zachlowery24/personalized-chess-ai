import pytest

from backend.app.services.engine_analysis import (
    PositionAnalysis,
    calculate_centipawn_loss,
)


@pytest.mark.parametrize("color, before_cp, after_cp, expected", [
    ("white", 57, -11, 68),
    ("black", -11, 181, 192),
    ("white", -100, -150, 50),
    ("black", -150, -100, 50),
    ("white", 20, 50, 0),
    ("black", 50, 20, 0),
    ("white", 0, 0, 0),
    ("black", 0, 0, 0),
    ("white", 0, -25, 25),
    ("black", 0, 25, 25),
])
def test_centipawn_loss_uses_moving_players_perspective(
    color, before_cp, after_cp, expected,
):
    before = PositionAnalysis(None, before_cp, None, 12)
    after = PositionAnalysis(None, after_cp, None, 12)
    assert calculate_centipawn_loss(before, after, color=color) == expected


@pytest.mark.parametrize("color", ["white", "black"])
@pytest.mark.parametrize("before_cp, before_mate, after_cp, after_mate", [
    (20, None, None, 3),
    (None, 3, 20, None),
    (None, 3, None, 2),
    (None, -3, None, -2),
    (20, None, None, 0),
])
def test_mate_transitions_have_no_centipawn_loss(
    color, before_cp, before_mate, after_cp, after_mate,
):
    before = PositionAnalysis(None, before_cp, before_mate, 12)
    after = PositionAnalysis(None, after_cp, after_mate, 12)
    assert calculate_centipawn_loss(before, after, color=color) is None


@pytest.mark.parametrize("color", ["White", "BLACK", "", "green", None])
def test_centipawn_loss_rejects_invalid_color(color):
    position = PositionAnalysis(None, 0, None, 12)
    with pytest.raises(ValueError, match="color must be 'white' or 'black'"):
        calculate_centipawn_loss(position, position, color=color)
