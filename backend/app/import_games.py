import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
from backend.app.database import get_session_factory

from backend.app.services.game_import import (
    GameProcessingError,
    GameRetrievalError,
    GameStorageError,
    import_recent_games,
)
from backend.app.services.game_processing import group_games_by_time_class


def save_games(games: list[dict], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            json.dump(games, output_file, indent=2)
            output_file.write("\n")

        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description="Import Chess.com games and extract move positions."
    )
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument(
        "--count", type=int, default=5, help="Number of games to import"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save processed games as JSON, replacing any existing file",
    )
    parser.add_argument(
        "--save-db", action="store_true",
        help="Save playable games to PostgreSQL after processing succeeds",
    )
    args = parser.parse_args()

    if args.count < 0:
        parser.error("--count must be nonnegative")

    if not args.username.strip():
        parser.error("username must not be blank")

    try:
        if args.save_db:
            result = import_recent_games(
                args.username, args.count, session_factory=get_session_factory()
            )
        else:
            result = import_recent_games(args.username, args.count)
    except httpx.HTTPStatusError as error:
        print(
            f"Import failed: Chess.com returned HTTP {error.response.status_code}.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except httpx.RequestError:
        print(
            "Import failed: could not reach Chess.com or complete the request.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except GameRetrievalError as error:
        print(f"Import failed while retrieving games: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    except GameProcessingError as error:
        print(f"Import failed while processing games: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except GameStorageError:
        print("Import failed: could not save games to PostgreSQL.", file=sys.stderr)
        raise SystemExit(1) from None

    processed_games = result["games"]
    buckets = group_games_by_time_class(processed_games)

    if args.output is not None:
        try:
            save_games(processed_games, args.output)
        except OSError as error:
            print(f"Could not save processed games: {error}", file=sys.stderr)
            raise SystemExit(1) from None

    print(f"Imported {result['imported_count']} games")
    print(f"Processed {result['processed_count']} games")
    print(f"Skipped {result['skipped_count']} games without moves")

    for time_class, bucket in buckets.items():
        print(f"{time_class}: {len(bucket)} games")

    total_positions = sum(len(game["moves"]) for game in processed_games)
    print(f"Extracted {total_positions} move records")
    if args.save_db:
        print(f"Persisted {result['processed_count']} games to PostgreSQL (including existing games)")

    if args.output is not None:
        print(f"Saved processed games to {args.output}")


if __name__ == "__main__":
    main()
