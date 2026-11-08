from datetime import UTC, datetime

from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.models.game import Game
from backend.app.repositories.players import get_or_create_player



def get_or_create_game(session: Session, game: dict) -> Game:
    """Store an already-validated, playable Chess.com game."""
    source = "chess.com"
    ended_at = datetime.fromtimestamp(game["end_time"], tz=UTC)

    white_player = get_or_create_player(
        session, source, game["white"]["username"]
    )
    black_player = get_or_create_player(
        session, source, game["black"]["username"]
    )

    values = {
        "source": source,
        "source_url": game["url"],
        "white_player_id": white_player.id,
        "black_player_id": black_player.id,
        "white_result": game["white"]["result"],
        "black_result": game["black"]["result"],
        "time_class": game["time_class"],
        "rules": game["rules"],
        "ended_at": ended_at,
        "pgn": game["pgn"],
    }

    statement = (
        insert(Game)
        .values(**values)
        .on_conflict_do_nothing(
            constraint="uq_games_source_source_url"
        )
    )
    session.execute(statement)

    query = select(Game).where(
        Game.source == source,
        Game.source_url == game["url"],
    )
    return session.execute(query).scalar_one()


def get_game_by_id(session: Session, game_id: int) -> Game | None:
    return session.get(Game, game_id)


def list_games_for_player(
    session: Session,
    player_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
    time_class: str | None = None,
) -> list[Game]:
    statement = select(Game).where(
    or_(
        Game.white_player_id == player_id,
        Game.black_player_id == player_id,
    )
)
    if time_class is not None:
        statement = statement.where(Game.time_class == time_class)

    statement = (
        statement
        .order_by(Game.ended_at.desc(), Game.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement).all())