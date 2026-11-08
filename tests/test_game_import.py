from backend.app.services import game_import
import pytest


def test_import_recent_games_processes_and_skips(monkeypatch):
    def fake_fetch(username, count):
        assert username == "test-player"
        assert count == 2

        return [
            {
                "rules": "chess",
                "url": "https://www.chess.com/game/live/123",
                "white": {"username": "test-player", "result": "win"},
                "black": {"username": "opponent", "result": "resigned"},
                "time_class": "blitz",
                "end_time": 1234567890,
                "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
            },
            {
                "rules": "chess",
                "white": {"username": "test-player"},
                "black": {"username": "opponent"},
                "pgn": '[Event "Empty"]\n\n*',
            },
        ]

    monkeypatch.setattr(game_import, "get_recent_games", fake_fetch)

    result = game_import.import_recent_games("test-player", 2)

    assert result["imported_count"] == 2
    assert result["processed_count"] == 1
    assert result["skipped_count"] == 1
    assert len(result["games"]) == 1

    processed = result["games"][0]
    assert processed["user_color"] == "white"
    assert [move["uci"] for move in processed["moves"]] == ["e2e4", "e7e5"]

def test_import_recent_games_returns_empty_summary(monkeypatch):
    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [],
    )

    result = game_import.import_recent_games("test-player", 5)

    assert result == {
        "imported_count": 0,
        "processed_count": 0,
        "skipped_count": 0,
        "games": [],
    }


def test_import_recent_games_propagates_retrieval_error(monkeypatch):
    def failed_fetch(username, count):
        raise ValueError("Invalid archive response")

    monkeypatch.setattr(game_import, "get_recent_games", failed_fetch)

    with pytest.raises(game_import.GameRetrievalError, match="Invalid archive response"):
        game_import.import_recent_games("test-player", 5)

def test_import_recent_games_does_not_return_partial_results(monkeypatch):
    valid_game = {
        "rules": "chess",
        "url": "https://www.chess.com/game/live/123",
        "white": {"username": "test-player", "result": "win"},
        "black": {"username": "opponent", "result": "resigned"},
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }
    invalid_game = {**valid_game, "rules": "chess960"}

    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [valid_game, invalid_game],
    )

    with pytest.raises(game_import.GameProcessingError, match="Only standard chess is supported"):
        game_import.import_recent_games("test-player", 2)

@pytest.fixture
def storage_game():
    return {
        "rules": "chess", "url": "https://www.chess.com/game/live/123",
        "white": {"username": "test-player", "result": "win"},
        "black": {"username": "opponent", "result": "resigned"},
        "time_class": "blitz", "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }


def test_storage_receives_only_playable_original_records(monkeypatch, storage_game):
    empty = {**storage_game, "pgn": '[Event "Empty"]\n\n*'}
    monkeypatch.setattr(game_import, "get_recent_games", lambda *args: [storage_game, empty])
    factory = object()
    calls = []

    def save(records, supplied_factory):
        calls.append((records, supplied_factory))
        return [42]

    monkeypatch.setattr(game_import, "save_imported_games", save)
    result = game_import.import_recent_games("test-player", 2, session_factory=factory)
    assert calls == [([storage_game], factory)]
    assert result["processed_count"] == result["skipped_count"] == 1


def test_processing_failure_never_starts_storage(monkeypatch, storage_game):
    invalid = {**storage_game, "rules": "chess960"}
    monkeypatch.setattr(game_import, "get_recent_games", lambda *args: [storage_game, invalid])
    monkeypatch.setattr(game_import, "save_imported_games", lambda *args: pytest.fail("Must not save partial import"))
    with pytest.raises(game_import.GameProcessingError):
        game_import.import_recent_games("test-player", 2, session_factory=object())


@pytest.mark.parametrize("persist", [False, True])
def test_empty_import_never_starts_storage(monkeypatch, persist):
    monkeypatch.setattr(game_import, "get_recent_games", lambda *args: [])
    monkeypatch.setattr(game_import, "save_imported_games", lambda *args: pytest.fail("No records to save"))
    result = game_import.import_recent_games("test-player", 2, session_factory=object() if persist else None)
    assert result["games"] == []


def test_database_failure_is_wrapped(monkeypatch, storage_game):
    from sqlalchemy.exc import SQLAlchemyError

    monkeypatch.setattr(game_import, "get_recent_games", lambda *args: [storage_game])
    original = SQLAlchemyError("Internal database details")

    def fail(*args):
        raise original

    monkeypatch.setattr(game_import, "save_imported_games", fail)
    with pytest.raises(game_import.GameStorageError) as error:
        game_import.import_recent_games("test-player", 1, session_factory=object())
    assert error.value.__cause__ is original
