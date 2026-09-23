import pytest

from backend.app.services.game_processing import group_games_by_time_class, get_user_color, process_game


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


@pytest.mark.parametrize(
    "username, expected",
    [
        (" Hikaru ", "white"),
        ("OPPONENT", "black"),
    
    ],
)
def test_get_user_color(username, expected):
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},

    }
    assert get_user_color(game, username) == expected

def test_get_user_color_rejects_unrelated_user():
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},

    }
    with pytest.raises(ValueError, match="User is not a player"):
        get_user_color(game, "someone-else")


def test_process_game_combines_metadata_and_moves():
    game = {
        "url": "https://www.chess.com/game/live/123",
        "white": {"username": "Hikaru", "result": "win"},
        "black": {"username": "Opponent", "result": "resigned"},
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }

    result = process_game(game, " OPPONENT ")

    assert result is not None
    assert result["source"] == "chess.com"
    assert result["source_url"] == game["url"]
    assert result["username"] == "opponent"
    assert result["user_color"] == "black"
    assert result["white_username"] == "Hikaru"
    assert result["black_username"] == "Opponent"
    assert result["user_result"] == "resigned"
    assert result["time_class"] == "blitz"
    assert result["end_time"] == game["end_time"]
    assert result["pgn"] == game["pgn"]
    assert [move["uci"] for move in result["moves"]] == ["e2e4", "e7e5"]


def test_process_game_skips_game_without_moves():
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},
        "pgn": '[Event "Empty"]\n\n*',
    }

    assert process_game(game, "hikaru") is None


def test_process_game_rejects_multiple_playable_games():
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},
        "pgn": """
[Event "First"]

1. e4 e5 *

[Event "Second"]

1. d4 d5 *
""",
    }

    with pytest.raises(ValueError, match="Expected one playable game"):
        process_game(game, "hikaru")

