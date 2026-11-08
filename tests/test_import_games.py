import sys
import json
import pytest
import httpx

from backend.app import import_games
from backend.app.services import game_import



def test_import_command(monkeypatch, capsys):
    # argv[0] is the program name; argparse reads the arguments after it.
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player", "--count", "2"])

    def fake_get_recent_games(username, count):
        assert username == "test-player"
        assert count == 2

        return [{
            "url": "https://www.chess.com/game/live/123",
            "white": {"username": "test-player", "result": "win"},
            "black": {"username": "opponent", "result": "resigned"},
            "rules": "chess",
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0',
        }]

    # Replace the name main() uses, rather than the original service definition.
    monkeypatch.setattr(game_import, "get_recent_games", fake_get_recent_games)

    import_games.main()

    output = capsys.readouterr().out
    assert "Imported 1 games" in output
    assert "blitz: 1 games" in output
    assert "Extracted 4 move records" in output
    assert "Processed 1 games" in output
    assert "Skipped 0 games without moves" in output

def test_import_command_skips_games_without_moves(monkeypatch, capsys):

    monkeypatch.setattr(sys, "argv", ["import_games", "test-player", "--count", "2"])
    def fake_get_games(username, count):
        assert username == "test-player"
        assert count == 2
        return[{
            "white": {"username": "test-player"},
            "black": {"username": "opponent"},
            "rules": "chess",
            "time_class": "rapid",
            "pgn": '[Event "Empty"]\n\n*',
        },
        {
            "url": "https://www.chess.com/game/live/123",
            "white": {"username": "test-player", "result": "win"},
            "black": {"username": "opponent", "result": "resigned"},
            "rules": "chess",
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0',
        }]
    monkeypatch.setattr(game_import, "get_recent_games", fake_get_games)
    
    import_games.main()
    
    output = capsys.readouterr().out
    assert "Imported 2 games" in output
    assert "Processed 1 games" in output
    assert "Skipped 1 games without moves" in output
    assert "blitz: 1 games" in output
    assert "Extracted 4 move records" in output
    assert "rapid:" not in output
    
def test_import_command_exports_json(monkeypatch, capsys, tmp_path):
    output_path = tmp_path / "exports" / "games.json"

    monkeypatch.setattr(sys, "argv", [
        "import_games", "test-player", "--count", "1",
        "--output", str(output_path),
    ])

    def fake_get_recent_games(username, count):
        assert username == "test-player"
        assert count == 1
        return [{
            "url": "https://www.chess.com/game/live/123",
            "white": {"username": "test-player", "result": "win"},
            "black": {"username": "opponent", "result": "resigned"},
            "rules": "chess",
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
        }]

    monkeypatch.setattr(game_import, "get_recent_games", fake_get_recent_games)

    import_games.main()

    saved_games = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(saved_games) == 1
    assert saved_games[0]["username"] == "test-player"
    assert saved_games[0]["user_color"] == "white"
    assert [move["uci"] for move in saved_games[0]["moves"]] == [
        "e2e4", "e7e5",
    ]
    assert f"Saved processed games to {output_path}" in capsys.readouterr().out


def test_import_command_rejects_negative_count(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["import_games", "test-player", "--count", "-1"]
    )

    def unexpected_fetch(*args, **kwargs):
        pytest.fail("Invalid count must not trigger game retrieval")

    monkeypatch.setattr(game_import, "get_recent_games", unexpected_fetch)

    with pytest.raises(SystemExit) as error:
        import_games.main()

    assert error.value.code == 2
    assert "--count must be nonnegative" in capsys.readouterr().err

def test_import_command_handles_http_error(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["import_games", "test-player", "--count", "2"]
    )

    def failed_fetch(username, count):
        request = httpx.Request(
            "GET", "https://api.chess.com/pub/player/test-player/games/archives"
        )
        response = httpx.Response(429, request=request)
        response.raise_for_status()

    monkeypatch.setattr(game_import, "get_recent_games", failed_fetch)

    with pytest.raises(SystemExit) as error:
        import_games.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "Import failed: Chess.com returned HTTP 429." in captured.err
    assert captured.out == ""



def test_import_command_handles_timeout(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["import_games", "test-player", "--count", "2"]
    )

    def failed_fetch(username, count):
        raise httpx.ReadTimeout("Response timed out")

    monkeypatch.setattr(game_import, "get_recent_games", failed_fetch)

    with pytest.raises(SystemExit) as error:
        import_games.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert (
        "Import failed: could not reach Chess.com or complete the request."
        in captured.err
    )
    assert captured.out == ""


@pytest.fixture
def cli_game():
    return {
        "rules": "chess",
        "url": "https://www.chess.com/game/live/123",
        "white": {"username": "test-player", "result": "win"},
        "black": {"username": "opponent", "result": "resigned"},
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }


def test_import_command_handles_invalid_response(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player"])

    def failed_fetch(username, count):
        raise ValueError("Unexpected archive response")

    monkeypatch.setattr(game_import, "get_recent_games", failed_fetch)

    with pytest.raises(SystemExit) as error:
        import_games.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "Import failed while retrieving games:" in captured.err
    assert "Unexpected archive response" in captured.err
    assert captured.out == ""


def test_processing_failure_preserves_existing_export(
    monkeypatch, capsys, tmp_path, cli_game
):
    output_path = tmp_path / "games.json"
    original = '[{"previous": true}]\n'
    output_path.write_text(original, encoding="utf-8")

    # The first game succeeds; the second fails validation.
    invalid_game = {**cli_game, "rules": "chess960"}

    monkeypatch.setattr(sys, "argv", [
        "import_games", "test-player",
        "--output", str(output_path),
    ])
    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [cli_game, invalid_game],
    )

    with pytest.raises(SystemExit) as error:
        import_games.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "Import failed while processing games:" in captured.err
    assert captured.out == ""
    assert output_path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("count", [0, 5])
def test_import_command_exports_empty_results(
    monkeypatch, capsys, tmp_path, count
):
    output_path = tmp_path / "empty.json"

    monkeypatch.setattr(sys, "argv", [
        "import_games", "test-player", "--count", str(count),
        "--output", str(output_path),
    ])

    def empty_fetch(username, requested_count):
        assert requested_count == count
        return []

    monkeypatch.setattr(game_import, "get_recent_games", empty_fetch)

    import_games.main()

    assert json.loads(output_path.read_text(encoding="utf-8")) == []
    captured = capsys.readouterr()
    assert "Processed 0 games" in captured.out
    assert "Extracted 0 move records" in captured.out
    assert captured.err == ""


def test_import_command_does_not_save_without_output(
    monkeypatch, cli_game
):
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player"])
    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [cli_game],
    )

    def unexpected_save(*args, **kwargs):
        pytest.fail("No file should be saved without --output")

    monkeypatch.setattr(import_games, "save_games", unexpected_save)

    import_games.main()


def test_import_command_replaces_existing_export(
    monkeypatch, tmp_path, cli_game
):
    output_path = tmp_path / "games.json"
    output_path.write_text("previous contents", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "import_games", "test-player", "--output", str(output_path),
    ])
    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [cli_game],
    )

    import_games.main()

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["source_url"] == cli_game["url"]
    assert len(saved[0]["moves"]) == 2


def test_export_failure_preserves_existing_file(
    monkeypatch, capsys, tmp_path, cli_game
):
    output_path = tmp_path / "games.json"
    original = '[{"previous": true}]\n'
    output_path.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "import_games", "test-player", "--output", str(output_path),
    ])
    monkeypatch.setattr(
        game_import,
        "get_recent_games",
        lambda username, count: [cli_game],
    )

    def failed_dump(data, file, **kwargs):
        file.write("[")  # Simulate failure after a partial write.
        raise OSError("Disk full")

    monkeypatch.setattr(import_games.json, "dump", failed_dump)

    with pytest.raises(SystemExit) as error:
        import_games.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "Could not save processed games: Disk full" in captured.err
    assert captured.out == ""
    assert output_path.read_text(encoding="utf-8") == original
    assert list(tmp_path.iterdir()) == [output_path]


def test_cli_passes_database_factory_when_requested(monkeypatch, capsys):
    factory = object()
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player", "--save-db"])
    monkeypatch.setattr(import_games, "get_session_factory", lambda: factory)

    def fake_import(username, count, *, session_factory):
        assert (username, count) == ("test-player", 5)
        assert session_factory is factory
        return {"imported_count": 0, "processed_count": 0, "skipped_count": 0, "games": []}

    monkeypatch.setattr(import_games, "import_recent_games", fake_import)
    import_games.main()
    assert "Persisted 0 games" in capsys.readouterr().out


def test_cli_storage_failure_does_not_export(monkeypatch, capsys, tmp_path):
    from backend.app.services.game_import import GameStorageError

    output = tmp_path / "existing.json"
    output.write_text("previous export", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player", "--save-db", "--output", str(output)])
    monkeypatch.setattr(import_games, "get_session_factory", lambda: object())

    def fail(*args, **kwargs):
        raise GameStorageError("private details")

    monkeypatch.setattr(import_games, "import_recent_games", fail)
    with pytest.raises(SystemExit) as error:
        import_games.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Import failed: could not save games to PostgreSQL.\n"
    assert output.read_text(encoding="utf-8") == "previous export"
