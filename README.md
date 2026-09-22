# Personalized Chess AI

A chess analysis project that imports a player's games and prepares them
for personalized feedback. The long-term goal is to identify playing
tendencies and build a bot that approximates the player's style.

## Current Status

Milestone 1: Chess.com import and PGN processing.

Implemented:
- Discover a player's monthly Chess.com archives.
- Retrieve recent games across months, newest first.
- Group games by time class.
- Parse individual and multi-game PGNs, skipping games without moves.
- Extract move notation and board positions before and after each move.
- Run the pipeline from the command line.

## Setup

Requires uv and Python 3.12. Run commands from the repository root.

```sh
uv sync
```

The project pins Python 3.12 in `.python-version`. Dependencies are
declared in `pyproject.toml` and locked in `uv.lock`.

## Usage

```sh
uv run python -m backend.app.import_games hikaru --count 5
```

Replace `hikaru` with a Chess.com username. `--count` defaults to 5.

Example output (counts vary):

```text
Imported 5 games
blitz: 5 games
Extracted 499 move records
```

Each move record represents one player's move, or ply, and includes
its color, UCI and SAN notation, and FEN positions before and after it.

The importer returns up to the requested number of games. Fewer may be
available. Requests use Chess.com's public API; no API key is required.

## Tests

```sh
uv run python -m pytest
```

Tests cover retrieval, request failures, grouping, PGN parsing,
move-position extraction, and the CLI workflow. Network calls are
simulated so tests do not depend on Chess.com availability.

## Project Structure

```text
backend/
  app/
    import_games.py          # CLI entry point
    services/
      chesscom.py            # Chess.com API requests
      game_processing.py     # Grouping imported game records
      pgn.py                 # PGN parsing and move-position extraction
tests/
  test_chesscom.py
  test_game_processing.py
  test_pgn.py
  test_import_games.py
```

Retrieval and processing are separate so the same service functions
can later be reused by web endpoints and background jobs.

## Current Limitations

- Chess.com is the only supported source.
- Results are processed in memory; the CLI prints a summary.
- No database, web API, frontend, or Stockfish analysis yet.
- PGN parsing uses python-chess's forgiving parser; it is not strict
  validation of every input token.
- Automated retries and persistent caching are not implemented.

## Next Steps

- Define a consistent processed-game record.
- Preserve game metadata alongside extracted moves.
- Add persistence and FastAPI endpoints once the pipeline format is stable.
- Integrate Stockfish analysis.
- Add Lichess support and personalized feedback.

## References

- [Chess.com Published-Data API](https://www.chess.com/news/view/published-data-api)
- [python-chess documentation](https://python-chess.readthedocs.io/)