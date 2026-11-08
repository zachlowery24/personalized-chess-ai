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
        "rules": "chess",
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
        "rules": "chess",
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},
        "pgn": '[Event "Empty"]\n\n*',
    }

    assert process_game(game, "hikaru") is None


def test_process_game_rejects_multiple_playable_games():
    game = {
        "rules": "chess",
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

@pytest.mark.parametrize(
    "black_player, message",
    [
        (None, "black player must be a dictionary"),
        ("opponent", "black player must be a dictionary"),
        ({}, "black username must be a nonempty string"),
        ({"username": ""}, "black username must be a nonempty string"),
        ({"username": "   "}, "black username must be a nonempty string"),
        ({"username": 123}, "black username must be a nonempty string"),
    ],
)
def test_get_user_color_validates_opponent_before_returning(
    black_player, message
):
    game = {
        "white": {"username": "Hikaru"},
        "black": black_player,
    }

    with pytest.raises(ValueError, match=message):
        get_user_color(game, "hikaru")

@pytest.mark.parametrize("missing_color", ["white", "black"])
def test_get_user_color_rejects_missing_player(missing_color):
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},
    }
    del game[missing_color]

    with pytest.raises(
        ValueError, match=f"{missing_color} player must be a dictionary"
    ):
        get_user_color(game, "hikaru")


@pytest.mark.parametrize("username", [None, 123, "", " \t\n"])
def test_get_user_color_rejects_invalid_username(username):
    game = {
        "white": {"username": "Hikaru"},
        "black": {"username": "Opponent"},
    }

    with pytest.raises(ValueError, match="username must be a nonempty string"):
        get_user_color(game, username)


@pytest.mark.parametrize("game", [None, [], "not a game", 123])
def test_get_user_color_rejects_non_dictionary_game(game):
    with pytest.raises(ValueError, match="game must be a dictionary"):
        get_user_color(game, "hikaru")

@pytest.fixture
def valid_game():
    return {
        "rules": "chess",
        "url": "https://www.chess.com/game/live/123",
        "white": {"username": "Hikaru", "result": "win"},
        "black": {"username": "Opponent", "result": "resigned"},
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }


@pytest.mark.parametrize("end_time", [None, -1, True, 1.5, "123"])
def test_process_game_rejects_invalid_end_time(valid_game, end_time):
    valid_game["end_time"] = end_time

    with pytest.raises(
        ValueError, match="end_time must be a nonnegative integer"
    ):
        process_game(valid_game, "hikaru")


def test_process_game_rejects_missing_end_time(valid_game):
    del valid_game["end_time"]

    with pytest.raises(
        ValueError, match="end_time must be a nonnegative integer"
    ):
        process_game(valid_game, "hikaru")

@pytest.mark.parametrize("field", ["url", "time_class"])
@pytest.mark.parametrize("value", [None, "", " \t", 123])
def test_process_game_rejects_invalid_text_metadata(valid_game, field, value):
    valid_game[field] = value

    with pytest.raises(ValueError, match=f"{field} must be a nonempty string"):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("field", ["url", "time_class"])
def test_process_game_rejects_missing_text_metadata(valid_game, field):
    del valid_game[field]

    with pytest.raises(ValueError, match=f"{field} must be a nonempty string"):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("color", ["white", "black"])
@pytest.mark.parametrize("value", [None, "", " \t", 123])
def test_process_game_rejects_invalid_player_result(valid_game, color, value):
    valid_game[color]["result"] = value

    with pytest.raises(
        ValueError,
        match=f"{color} result must be a nonempty string",
    ):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("color", ["white", "black"])
def test_process_game_rejects_missing_player_result(valid_game, color):
    del valid_game[color]["result"]

    with pytest.raises(
        ValueError,
        match=f"{color} result must be a nonempty string",
    ):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("color", ["white", "black"])
def test_process_game_rejects_overlong_player_result(valid_game, color):
    valid_game[color]["result"] = "x" * 33

    with pytest.raises(
        ValueError,
        match=f"{color} result must not exceed 32 characters",
    ):
        process_game(valid_game, "hikaru")

def test_process_game_rejects_missing_pgn(valid_game):
    del valid_game["pgn"]

    with pytest.raises(ValueError, match="PGN must be a nonempty string"):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("rules", ["chess960", "crazyhouse", None, ""])
def test_process_game_rejects_unsupported_rules(valid_game, rules):
    valid_game["rules"] = rules

    with pytest.raises(ValueError, match="Only standard chess is supported"):
        process_game(valid_game, "hikaru")


@pytest.mark.parametrize("variant", ["Chess960", "Crazyhouse"])
def test_process_game_rejects_variant_pgn_with_standard_metadata(valid_game, variant):
    # The metadata says standard chess, but the PGN selects different rules.
    valid_game["pgn"] = f'[Variant "{variant}"]\n\n1. e4 e5 *'

    with pytest.raises(ValueError, match="PGN must describe standard chess"):
        process_game(valid_game, "hikaru")


def test_process_game_accepts_standard_custom_starting_position(valid_game):
    valid_game["pgn"] = (
        '[SetUp "1"]\n'
        '[FEN "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"]\n'
        '[Result "1-0"]\n\n'
        '1. O-O 1-0'
    )

    result = process_game(valid_game, "hikaru")

    assert result is not None
    assert result["rules"] == "chess"
    assert len(result["moves"]) == 1
    assert result["moves"][0]["uci"] == "e1g1"
    assert result["moves"][0]["fen_before"] == (
        "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    )
