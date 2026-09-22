import pytest

from backend.app.services.game_processing import group_games_by_time_class


def test_groups_games_by_time_class():
    blitz_game = {"time_class": "blitz", "end_time": 300}
    rapid_game = {"time_class": "rapid", "end_time": 200}
    older_blitz_game = {"time_class": "blitz", "end_time": 100}

    result = group_games_by_time_class(
        [blitz_game, rapid_game, older_blitz_game]
    )

    assert result == {
        "blitz": [blitz_game, older_blitz_game],
        "rapid": [rapid_game],
    }


def test_empty_games_returns_empty_buckets():
    assert group_games_by_time_class([]) == {}


@pytest.mark.parametrize(
    "game",
    [
        pytest.param({}, id="missing-field"),
        pytest.param({"time_class": ""}, id="empty-string"),
        pytest.param({"time_class": " \t\n"}, id="whitespace-only"),
        pytest.param({"time_class": None}, id="none"),
        pytest.param({"time_class": 123}, id="integer"),
        pytest.param({"time_class": False}, id="boolean"),
        pytest.param({"time_class": []}, id="list"),
        pytest.param({"time_class": {}}, id="dictionary"),
    ],
)
def test_rejects_invalid_time_class(game):
    with pytest.raises(ValueError, match="^time_class must be a nonempty string$"):
        group_games_by_time_class([game])
