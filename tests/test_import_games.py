import sys

from backend.app import import_games


def test_import_command(monkeypatch, capsys):
    # argv[0] is the program name; argparse reads the arguments after it.
    monkeypatch.setattr(sys, "argv", ["import_games", "test-player", "--count", "2"])

    def fake_get_recent_games(username, count):
        assert username == "test-player"
        assert count == 2
        return [{"time_class": "blitz", "pgn": "1. e4 e5 2. Nf3 Nc6 *"}]

    # Replace the name main() uses, rather than the original service definition.
    monkeypatch.setattr(import_games, "get_recent_games", fake_get_recent_games)

    import_games.main()

    output = capsys.readouterr().out
    assert "Imported 1 games" in output
    assert "blitz: 1 games" in output
    assert "Extracted 4 move records" in output
