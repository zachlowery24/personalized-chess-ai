# Personalized Chess AI

A chess analysis project that imports a player's games and prepares them
for personalized feedback. The long-term goal is to identify playing
tendencies and build a bot that approximates the player's style.

## Current Status

A working Chess.com import and PGN-processing pipeline, available through a
command-line interface and FastAPI. Database persistence is the next milestone.

Implemented:

- Discover a player's monthly Chess.com archives.
- Retrieve recent games across months, newest first.
- Group games by time class.
- Parse individual and multi-game PGNs, skipping games without moves.
- Extract move notation and board positions before and after each move.
- Run the pipeline from the command line.
- Preserve game metadata and extracted moves in a consistent processed record.
- Validate archive URLs, archive ordering, completion timestamps, player data,
  required metadata, and standard-chess rules.
- Export processed records to JSON and report expected failures clearly.
- Serve imports through a validated HTTP API using the same import service as the CLI.

## Setup

Requires uv and Python 3.12. Run commands from the repository root.

```sh
uv sync
```

The project pins Python 3.12 in `.python-version`. Dependencies are
declared in `pyproject.toml` and locked in `uv.lock`.

## CLI Usage

```sh
uv run python -m backend.app.import_games hikaru --count 5
```

Replace `hikaru` with a Chess.com username. `--count` defaults to 5.
It limits imported games before processing, so skipped games can leave fewer
processed records. A count of zero succeeds with an empty result.

To save the processed games:

```sh
uv run python -m backend.app.import_games hikaru --count 5 --output data/processed/hikaru.json
```

Without `--output`, the command prints a summary and writes no file. With it,
the command creates missing parent directories and writes a JSON array.
An empty result is exported as `[]`.

An existing destination file is replaced. Export first writes a temporary file
in the same directory, then replaces the destination after writing succeeds.
Processing failures and failures while writing the temporary file leave an
existing export intact. Generated exports are local data; keep them out of commits.

Example output (counts vary):

```text
Imported 5 games
Processed 5 games
Skipped 0 games without moves
blitz: 5 games
Extracted 499 move records
```

Each move record represents one player's move, or ply, and includes
its color, UCI and SAN notation, and FEN positions before and after it.

The importer returns up to the requested number of games. Fewer may be
available. Requests use Chess.com's public API; no API key is required.

## HTTP API

Start the development server from the repository root:

```sh
uv run uvicorn backend.app.main:app --reload
```

The server listens at `http://127.0.0.1:8000`. Open
[interactive API documentation](http://127.0.0.1:8000/docs) to try requests,
or inspect the schema at `/openapi.json`. Stop the server with Control+C.
`--reload` is for local development.

### Health check

```sh
curl http://127.0.0.1:8000/health
```

`GET /health` returns HTTP `200` with `{"status":"ok"}`. It checks that the
application can respond; it does not contact Chess.com or test external services.

### Import games

```sh
curl -X POST http://127.0.0.1:8000/imports/chesscom \
  -H 'Content-Type: application/json' \
  -d '{"username":"hikaru","count":2}'
```

| Request field | Contract |
| --- | --- |
| `username` | Required string; surrounding whitespace is removed and the name is lowercased; blank values are rejected |
| `count` | Optional integer, defaults to `5`; API range is `1`–`100`; strings, booleans, and floats are rejected |

Unlike the CLI, the API does not accept a count of zero. The count limits fetched
games, not the number remaining after processing. Retrieval downloads whole
monthly archives, so the limit does not bound download size or request duration.

A successful request returns HTTP `200` with these fields:

| Response field | Meaning |
| --- | --- |
| `imported_count` | Number of fetched game records |
| `processed_count` | Number of playable games successfully processed |
| `skipped_count` | Number of records skipped because they contain no playable game |
| `games` | List of processed records, including nested move records described below |

For example, if the player has no available games:

```json
{
  "imported_count": 0,
  "processed_count": 0,
  "skipped_count": 0,
  "games": []
}
```

The endpoint waits for retrieval and processing to finish, then returns the
result. It does not create an export file, store games in a database, or enqueue
a background job. Pydantic validates the request and nested response records.

### API errors

| Status | Meaning |
| --- | --- |
| `422` | Request validation failed; the import service is not called |
| `404` | A requested Chess.com resource was not found; this need not mean the username is missing |
| `502` | Connection/request failure, other unsuccessful upstream response, invalid upstream data, or games that could not be processed |
| `503` | Chess.com returned `429` and is temporarily rate-limiting requests |
| `504` | A request to Chess.com timed out |

Handled service failures return a stable message without internal exception
details, for example:

```json
{"detail": "Chess.com did not respond in time."}
```

Request validation errors instead contain a `detail` list identifying invalid
fields. Processing failures do not return a partial collection of games.

## Processed Records

Each exported game includes:

| Fields | Contents |
| --- | --- |
| `source`, `source_url` | Provider and original game URL |
| `username`, `user_color` | Requested username normalized to lowercase and its color |
| `white_username`, `black_username` | Player names from the source record |
| `user_result` | Original result code for the requested player, such as `win` or `resigned` |
| `rules`, `time_class` | Standard-chess rules and time category |
| `end_time`, `pgn` | Completion timestamp and original PGN text |
| `moves` | All mainline moves from both players |

Each move contains `ply`, `color`, `uci`, `san`, `fen_before`, and `fen_after`.
Ply numbering starts at one within the game. Positions honor custom PGN starting
positions that use standard chess rules.

The general PGN parser supports multiple games. Processing a single Chess.com
record requires exactly one playable game: no-move games are skipped, while
multiple playable games are rejected. Category counts include processed games only.

## Validation and Errors

Archive URLs must match the expected Chess.com player endpoint and valid
four-digit-year/two-digit-month format. Archives must be unique and oldest first,
which makes early stopping during recent-game retrieval reliable. Monthly game
records must have nonnegative integer completion timestamps before sorting.

Processing validates both players, the requested user's membership in the game,
required text metadata, and the timestamp. Both source rules and the parsed PGN
must describe standard chess; unsupported variants stop the import.

Recorded PGN parsing errors are rejected rather than exporting a partial game.
The CLI reports handled HTTP, network, validation, and filesystem errors on
standard error. It stops without exporting a partial collection if a game fails
processing. Success summaries print only after any requested export succeeds.

| Exit code | Meaning |
| --- | --- |
| `0` | Successful run, including empty results |
| `1` | Handled retrieval, processing, or export failure |
| `2` | Invalid command-line arguments, such as a negative count or blank username |

## Tests

```sh
uv run python -m pytest
```

Tests cover retrieval, request failures, grouping, PGN parsing,
move-position extraction, metadata and variant validation, and the CLI workflow.
Export tests cover JSON contents and preservation of existing files on failure.
Network calls are simulated so tests do not depend on Chess.com availability;
file-writing tests use temporary directories.

API tests use FastAPI's `TestClient` without starting Uvicorn. They cover request
normalization, validation before service execution, error mappings, and a populated
response passing through the real shared service and PGN processor with fake
retrieval. Schema tests check nested game and move validation.

To run only the API tests:

```sh
uv run python -m pytest tests/test_api.py -v
```

## Project Structure

```text
backend/
  app/
    import_games.py          # CLI entry point
    main.py                  # FastAPI application and endpoints
    schemas/
      game_import.py         # Pydantic request and nested response models
    services/
      chesscom.py            # Chess.com API requests
      game_import.py         # Shared import workflow and stage-specific errors
      game_processing.py     # Validation, processed records, and grouping
      pgn.py                 # PGN parsing and move-position extraction
tests/
  test_api.py
  test_chesscom.py
  test_game_import.py
  test_game_import_schemas.py
  test_game_processing.py
  test_pgn.py
  test_import_games.py
```

The CLI and API call the same import service. Retrieval and processing remain
separate from terminal output, file export, and HTTP error handling.

## Current Limitations

- Chess.com is the only supported source.
- Processing is in memory; optional JSON export is the only persistence.
- Only standard chess is supported. An unsupported variant stops the import.
- No database, frontend, or Stockfish analysis yet.
- API imports run within the request; there is no background job queue or progress tracking.
- The API has no authentication or application-level rate limiting yet.
- PGN parsing uses python-chess's forgiving parser; it is not strict
  validation of every input token.
- Automated retries and persistent caching are not implemented.
- Validation checks required metadata types and presence, but does not fully
  cross-check PGN player names or results against source metadata.

## Next Steps

- Add PostgreSQL persistence and migrations for games and import history.
- Prevent duplicate imports and expose retrieval of saved games.
- Integrate Stockfish analysis.
- Add Lichess support and personalized feedback.

## References

- [Chess.com Published-Data API](https://www.chess.com/news/view/published-data-api)
- [python-chess documentation](https://python-chess.readthedocs.io/)
