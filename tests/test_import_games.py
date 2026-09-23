import sys
import json

from backend.app import import_games



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
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0',
        }]

    # Replace the name main() uses, rather than the original service definition.
    monkeypatch.setattr(import_games, "get_recent_games", fake_get_recent_games)

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
            "time_class": "rapid",
            "pgn": '[Event "Empty"]\n\n*',
        },
        {
            "url": "https://www.chess.com/game/live/123",
            "white": {"username": "test-player", "result": "win"},
            "black": {"username": "opponent", "result": "resigned"},
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 1-0',
        }]
    monkeypatch.setattr(import_games, "get_recent_games", fake_get_games)
    
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
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
        }]

    monkeypatch.setattr(import_games, "get_recent_games", fake_get_recent_games)

    import_games.main()

    saved_games = json.loads(output_path.read_text(encoding="utf-8"))

    assert len(saved_games) == 1
    assert saved_games[0]["username"] == "test-player"
    assert saved_games[0]["user_color"] == "white"
    assert [move["uci"] for move in saved_games[0]["moves"]] == [
        "e2e4", "e7e5",
    ]
    assert f"Saved processed games to {output_path}" in capsys.readouterr().out


