"""Transform imported game records without making network requests."""


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
   
