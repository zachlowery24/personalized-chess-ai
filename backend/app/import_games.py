from backend.app.services.chesscom import get_recent_games
from backend.app.services.game_processing import group_games_by_time_class
from backend.app.services.pgn import parse_pgn_games, extract_move_positions

import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Import Chess.com games and extract move positions."
    )
    parser.add_argument("username", help="Chess.com username")
    parser.add_argument("--count", type=int, default=5, help="Number of games to import")
    args = parser.parse_args()

    games = get_recent_games(args.username, args.count)
    buckets = group_games_by_time_class(games)

    print(f"Imported {len(games)} games")

    for time_class, bucket in buckets.items():
        print(f"{time_class}: {len(bucket)} games")

    total_positions = 0

    for game_record in games:
        parsed_games = parse_pgn_games(game_record["pgn"])

        for parsed_game in parsed_games:
            positions = extract_move_positions(parsed_game)
            total_positions += len(positions)

    print(f"Extracted {total_positions} move records")


if __name__ == "__main__":
    main()