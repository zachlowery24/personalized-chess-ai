import pytest
from pydantic import ValidationError

from backend.app.schemas.game_import import (
    GameImportRequest,
    GameImportResponse,
    MoveRecord,
)
from backend.app.services.game_processing import process_game



from backend.app.schemas.game_import import GameImportRequest


def test_request_normalizes_username_and_defaults_count():
    request = GameImportRequest(username=" Hikaru ")

    assert request.username == "hikaru"
    assert request.count == 5


@pytest.mark.parametrize("count", [1, 100])
def test_request_accepts_count_boundaries(count):
    request = GameImportRequest(username="hikaru", count=count)

    assert request.count == count


@pytest.mark.parametrize("count", [0, -1, 101, "5", True, 1.5, None])
def test_request_rejects_invalid_count(count):
    with pytest.raises(ValidationError) as error:
        GameImportRequest(username="hikaru", count=count)

    assert error.value.errors()[0]["loc"] == ("count",)


@pytest.mark.parametrize("username", ["", " \t\n", None, 123])
def test_request_rejects_invalid_username(username):
    with pytest.raises(ValidationError) as error:
        GameImportRequest(username=username)

    assert error.value.errors()[0]["loc"] == ("username",)


def test_request_requires_username():
    with pytest.raises(ValidationError):
        GameImportRequest()

def test_response_accepts_processed_game():
    raw_game = {
        "rules": "chess",
        "url": "https://www.chess.com/game/live/123",
        "white": {"username": "Hikaru", "result": "win"},
        "black": {"username": "Opponent", "result": "resigned"},
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }

    processed = process_game(raw_game, "hikaru")
    assert processed is not None

    payload = {
        "imported_count": 1,
        "processed_count": 1,
        "skipped_count": 0,
        "games": [processed],
    }

    response = GameImportResponse.model_validate(payload)

    assert response.games[0].user_color == "white"
    assert isinstance(response.games[0].moves[0], MoveRecord)
    assert response.games[0].moves[0].uci == "e2e4"
    assert response.model_dump() == payload


def test_response_rejects_invalid_nested_move():
    payload = {
        "imported_count": 1,
        "processed_count": 1,
        "skipped_count": 0,
        "games": [{
            "source": "chess.com",
            "source_url": "https://www.chess.com/game/live/123",
            "username": "hikaru",
            "user_color": "white",
            "white_username": "Hikaru",
            "black_username": "Opponent",
            "user_result": "win",
            "rules": "chess",
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": "1. e4 *",
            "moves": [{
                "ply": 1,
                "color": "purple",
                "uci": "e2e4",
                "san": "e4",
                "fen_before": "placeholder",
                "fen_after": "placeholder",
            }],
        }],
    }

    with pytest.raises(ValidationError) as error:
        GameImportResponse.model_validate(payload)

    assert error.value.errors()[0]["loc"] == (
        "games", 0, "moves", 0, "color",
    )