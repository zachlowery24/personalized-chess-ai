from backend.app.services.chesscom import get_recent_games
from backend.app.services.game_processing import group_games_by_time_class, process_game

import json
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="Import Chess.com games and extract move positions."
    )
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument("--count", type=int, default=5, help="Number of games to import")

    parser.add_argument(
        "--output",
        type=Path,
        help="Save processed games to a JSON file"
    )
    args = parser.parse_args()

    games = get_recent_games(args.username, args.count)
    processed_games = []

    for game in games:
        processed = process_game(game, args.username)

        if processed is not None:
            processed_games.append(processed)


    

    print(f"Imported {len(games)} games")
    print(f"Processed {len(processed_games)} games")
    print(f"Skipped {len(games) - len(processed_games)} games without moves")

    buckets = group_games_by_time_class(processed_games)

    for time_class, bucket in buckets.items():
        print(f"{time_class}: {len(bucket)} games")

    total_positions = sum(len(game["moves"]) for game in processed_games)
    print(f"Extracted {total_positions} move records")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)

        with args.output.open("w", encoding="utf-8") as output_file:
            json.dump(processed_games, output_file, indent=2)

        print(f"Saved processed games to {args.output}")

if __name__ == "__main__":
    main()