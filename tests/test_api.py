from fastapi.testclient import TestClient
from backend.app import main
import pytest
import httpx

from backend.app.main import app
from backend.app.services.game_import import GameProcessingError, GameRetrievalError
from backend.app.services import game_import


def test_import_endpoint_returns_processed_games_and_moves(monkeypatch):
    calls = []

    def fake_fetch(username, count):
        calls.append((username, count))
        return [{
            "rules": "chess",
            "url": "https://www.chess.com/game/live/123",
            "white": {"username": "Hikaru", "result": "win"},
            "black": {"username": "Opponent", "result": "resigned"},
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
        }]

    # Keep the service and processing real; replace only external retrieval.
    monkeypatch.setattr(game_import, "get_recent_games", fake_fetch)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": " Hikaru ", "count": 2},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert calls == [("hikaru", 2)]

    payload = response.json()
    assert payload["imported_count"] == 1
    assert payload["processed_count"] == 1
    assert payload["skipped_count"] == 0
    assert len(payload["games"]) == 1

    game = payload["games"][0]
    assert game["source"] == "chess.com"
    assert game["source_url"] == "https://www.chess.com/game/live/123"
    assert game["username"] == "hikaru"
    assert game["user_color"] == "white"
    assert game["white_username"] == "Hikaru"
    assert game["black_username"] == "Opponent"
    assert game["user_result"] == "win"
    assert game["rules"] == "chess"
    assert game["time_class"] == "blitz"
    assert game["end_time"] == 1234567890
    assert game["pgn"] == '[Result "1-0"]\n\n1. e4 e5 1-0'

    moves = game["moves"]
    assert len(moves) == 2
    assert [move["uci"] for move in moves] == ["e2e4", "e7e5"]
    assert [move["san"] for move in moves] == ["e4", "e5"]
    assert [move["color"] for move in moves] == ["white", "black"]
    assert [move["ply"] for move in moves] == [1, 2]
    assert moves[0]["fen_before"] == (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    assert moves[0]["fen_after"] == moves[1]["fen_before"]
    assert moves[1]["fen_after"] == (
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    )


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_import_endpoint_normalizes_request(monkeypatch):
    calls = []

    def fake_import(username, count):
        calls.append((username, count))
        return {
            "imported_count": 0,
            "processed_count": 0,
            "skipped_count": 0,
            "games": [],
        }

    monkeypatch.setattr(main, "import_recent_games", fake_import)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": " Hikaru ", "count": 2},
        )

    assert response.status_code == 200
    assert response.json() == {
        "imported_count": 0,
        "processed_count": 0,
        "skipped_count": 0,
        "games": [],
    }
    assert calls == [("hikaru", 2)]

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "   "},
        {"username": "hikaru", "count": 0},
        {"username": "hikaru", "count": 101},
        {"username": "hikaru", "count": "5"},
        {"username": "hikaru", "count": True},
    ],
)
def test_import_endpoint_rejects_invalid_request(monkeypatch, payload):
    def unexpected_import(*args, **kwargs):
        pytest.fail("Invalid input must not call the import service")

    monkeypatch.setattr(main, "import_recent_games", unexpected_import)

    with TestClient(main.app) as client:
        response = client.post("/imports/chesscom", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]

def test_import_endpoint_handles_timeout(monkeypatch):
    def timed_out_import(username, count):
        raise httpx.ReadTimeout("Response timed out")

    monkeypatch.setattr(main, "import_recent_games", timed_out_import)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": "hikaru", "count": 2},
        )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Chess.com did not respond in time."
    }

def test_import_endpoint_handles_connection_failure(monkeypatch):
    def failed_import(username, count):
        raise httpx.ConnectError("Connection failed")

    monkeypatch.setattr(main, "import_recent_games", failed_import)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": "hikaru", "count": 2},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not complete the request to Chess.com."
    }


@pytest.mark.parametrize(
    "upstream_status, expected_status, detail",
    [
        (
            404,
            404,
            "The requested Chess.com resource was not found.",
        ),
        (
            429,
            503,
            "Chess.com is temporarily rate-limiting requests. Try again later.",
        ),
        (
            500,
            502,
            "Chess.com returned an unsuccessful response.",
        ),
        (
            403,
            502,
            "Chess.com returned an unsuccessful response.",
        ),
    ],
)
def test_import_endpoint_handles_upstream_http_error(
    monkeypatch, upstream_status, expected_status, detail
):
    def failed_import(username, count):
        request = httpx.Request(
            "GET",
            "https://api.chess.com/pub/player/hikaru/games/archives",
        )
        response = httpx.Response(upstream_status, request=request)
        response.raise_for_status()

    monkeypatch.setattr(main, "import_recent_games", failed_import)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": "hikaru", "count": 2},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "error_type, detail",
    [
        (GameRetrievalError, "Chess.com returned invalid game data."),
        (
            GameProcessingError,
            "The games returned by Chess.com could not be processed.",
        ),
    ],
)
def test_import_endpoint_handles_service_errors(monkeypatch, error_type, detail):
    def failed_import(username, count):
        raise error_type("Internal diagnostic: malformed source record")

    monkeypatch.setattr(main, "import_recent_games", failed_import)

    with TestClient(main.app) as client:
        response = client.post(
            "/imports/chesscom",
            json={"username": "hikaru", "count": 2},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": detail}
    assert "Internal diagnostic" not in response.text
