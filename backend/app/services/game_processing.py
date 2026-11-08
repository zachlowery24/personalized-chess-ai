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
    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a nonempty string")

    if not isinstance(game, dict):
        raise ValueError("game must be a dictionary")

    username = username.strip().lower()
    player_names = {}

    for color in ("white", "black"):
        player = game.get(color)

        if not isinstance(player, dict):
            raise ValueError(f"{color} player must be a dictionary")

        player_name = player.get("username")

        if not isinstance(player_name, str) or not player_name.strip():
            raise ValueError(f"{color} username must be a nonempty string")

        player_names[color] = player_name.strip().lower()

    for color, player_name in player_names.items():
        if player_name == username:
            return color

    raise ValueError("User is not a player in this game")

def process_game(game: dict, username: str) -> dict | None:
    color = get_user_color(game, username)
    rules = game.get("rules")

    if rules != "chess":
        raise ValueError("Only standard chess is supported; rules must be 'chess'")

    parsed_games = parse_pgn_games(game.get("pgn"))

    if not parsed_games:
        return None

    if len(parsed_games) != 1:
        raise ValueError("Expected one playable game per Chess.com record")

    parsed_game = parsed_games[0]
    board = parsed_game.board()

    if board.uci_variant != "chess" or board.chess960:
        raise ValueError("PGN must describe standard chess")
    
    for field in ("url", "time_class"):
        value = game.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a nonempty string")

    for player_color in ("white", "black"):
        result = game[player_color].get("result")

        if not isinstance(result, str) or not result.strip():
            raise ValueError(
                f"{player_color} result must be a nonempty string"
            )

        if len(result) > 32:
            raise ValueError(
                f"{player_color} result must not exceed 32 characters"
            )

    user_result = game[color]["result"]

    end_time = game.get("end_time")

    if type(end_time) is not int or end_time < 0:
        raise ValueError("end_time must be a nonnegative integer")
    
    moves = extract_move_positions(parsed_game)

    

    return {
        "source": "chess.com",
        "source_url": game["url"],
        "username": username.strip().lower(),
        "user_color": color,
        "white_username": game["white"]["username"],
        "black_username": game["black"]["username"],
        "user_result": user_result,
        "time_class": game["time_class"],
        "end_time": end_time,
        "pgn": game["pgn"],
        "moves": moves,
        "rules": rules,
    }


   
