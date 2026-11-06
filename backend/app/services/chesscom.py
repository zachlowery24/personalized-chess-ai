"""Read public player data from Chess.com's Published-Data API."""

from contextlib import nullcontext
import re
from urllib.parse import quote

import httpx

BASE_URL = "https://api.chess.com/pub"
USER_AGENT = "personalized-chess-ai/0.1.0"


def get_player_archives(
    username: str, *, client: httpx.Client | None = None
) -> list[str]:
    """Return monthly archive URLs in the API's oldest-first order.

    Raises ValueError for blank usernames or an unexpected response format.
    HTTP and network failures propagate as HTTPX exceptions, so a failed
    request cannot be mistaken for a player with no archived games.

    An optional client supports connection reuse and offline tests. The caller
    owns that client; only clients created here are closed here.
    """
    username = username.strip().lower()
    if not username:
        raise ValueError("username must not be blank")

    url = f"{BASE_URL}/player/{quote(username, safe='')}/games/archives"
    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(timeout=10.0, follow_redirects=True)
    )
    with context as http_client:
        response = http_client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        payload = response.json()

    archives = payload.get("archives") if isinstance(payload, dict) else None
    if not isinstance(archives, list) or not all(
        isinstance(archive, str) for archive in archives
    ):
        raise ValueError("Chess.com response must contain an 'archives' list of strings")

    archive_pattern = re.compile(
        re.escape(f"{BASE_URL}/player/{quote(username, safe='')}/games/")
        + r"([0-9]{4})/(0[1-9]|1[0-2])"
    )
    previous_month = (0, 0)
    for archive in archives:
        match = archive_pattern.fullmatch(archive)
        if match is None or int(match[1]) == 0:
            raise ValueError("Chess.com returned an invalid monthly archive URL")
        archive_month = (int(match[1]), int(match[2]))
        if archive_month <= previous_month:
            raise ValueError("Chess.com archives must be unique and ordered oldest first")
        previous_month = archive_month
    return archives



def get_monthly_games(
        username: str, year: int, month: int, *, client:httpx.Client | None = None):
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    username = username.strip().lower()
    if not username:
        raise ValueError("username must not be blank")

    url = f"{BASE_URL}/player/{quote(username, safe ='')}/games/{year}/{month:02d}"

    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(timeout = 10.0, follow_redirects= True)
    )

    with context as http_client:
        response = http_client.get(url, headers ={"User-Agent": USER_AGENT})
        response.raise_for_status()
        payload = response.json()

    games = payload.get("games") if isinstance(payload, dict) else None

    if not isinstance(games, list) or not all(
        isinstance(game, dict) for game in games
    ):
        raise ValueError("Chess.com response must contain a 'games' list of dictionaries")

    for index, game in enumerate(games):
        end_time = game.get("end_time")
        if type(end_time) is not int or end_time < 0:
            raise ValueError(
                f"Chess.com game at index {index} must contain a nonnegative integer end_time"
            )

    return games

def get_recent_games(
        username: str, count: int, *, client:httpx.Client | None = None
):
    if count < 0:
        raise ValueError("count must not be negative")
    if count == 0:
        return []

    context = (
        nullcontext(client)
        if client is not None
        else httpx.Client(timeout = 10.0, follow_redirects= True)
    )

    with context as http_client:
        archives = get_player_archives(username, client = http_client)
        collected_games = []
        for archive_url in reversed(archives):
            _, year_text, month_text = archive_url.rsplit("/", 2)
            year = int(year_text)
            month = int(month_text)
            monthly_games = get_monthly_games(
                username, year, month, client = http_client
            )
            collected_games.extend(monthly_games)
            if len(collected_games) >= count:
                break
    collected_games.sort(key = lambda game: game["end_time"], reverse = True)
    return collected_games[:count]

            
