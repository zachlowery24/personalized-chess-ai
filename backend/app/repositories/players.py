from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.models.player import PlayerProfile


def get_or_create_player(
    session: Session,
    source: str,
    username: str,
) -> PlayerProfile:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a nonempty string")

    if not isinstance(username, str) or not username.strip():
        raise ValueError("username must be a nonempty string")

    source = source.strip().lower()
    username = username.strip().lower()

    if len(source) > 32 or len(username) > 255:
        raise ValueError("source or username exceeds its maximum length")

    statement = (
        insert(PlayerProfile)
        .values(source=source, username=username)
        .on_conflict_do_nothing(
            constraint="uq_player_profiles_source_username"
        )
    )
    session.execute(statement)

    query = select(PlayerProfile).where(
        PlayerProfile.source == source,
        PlayerProfile.username == username,
    )
    return session.execute(query).scalar_one()


def get_player_by_username(
    session: Session,
    source: str,
    username: str,
) -> PlayerProfile | None:
    statement = select(PlayerProfile).where(
        PlayerProfile.source == source.strip().lower(),
        PlayerProfile.username == username.strip().lower(),
    )

    return session.execute(statement).scalar_one_or_none()
