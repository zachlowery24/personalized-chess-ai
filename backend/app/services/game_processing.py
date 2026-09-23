from backend.app.services.pgn import extract_move_positions, parse_pgn_games


def group_games_by_time_class(games: list[dict]) -> dict[str, list[dict]]:
    """Group games by time_class, preserving their order within each group.

    Include only categories present in the input; empty input returns {}.
    Raise ValueError for a missing, blank, or non-string time_class.
    """

    buckets = {}
  
    for game in games:
        time_class = game.get("time_class")
        if not isinstance(time_class, str) or not time_class.strip():
            raise ValueError("time_class must be a nonempty string")
        if time_class not in buckets:
            buckets[time_class] = []
        buckets[time_class].append(game)

    return buckets

def get_user_color(game: dict, username: str) -> str:
    username = username.strip().lower()

    if game["white"]["username"].lower() == username:
        return "white"
    if game["black"]["username"].lower() == username:
        return "black"

    raise ValueError("User is not a player in this game")

def process_game(game: dict, username: str) -> dict | None:
    color = get_user_color(game, username)
    parsed_games = parse_pgn_games(game["pgn"])

    if not parsed_games:
        return None

    if len(parsed_games) != 1:
        raise ValueError("Expected one playable game per Chess.com record")

    moves = extract_move_positions(parsed_games[0])

    

    return {
        "source": "chess.com",
        "source_url": game["url"],
        "username": username.strip().lower(),
        "user_color": color,
        "white_username": game["white"]["username"],
        "black_username": game["black"]["username"],
        "user_result": game[color]["result"],
        "time_class": game["time_class"],
        "end_time": game["end_time"],
        "pgn": game["pgn"],
        "moves": moves,
    }


   
