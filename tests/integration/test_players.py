from uuid import uuid4

from sqlalchemy import func, select

from backend.app.models.player import PlayerProfile
from backend.app.repositories.players import get_or_create_player, get_player_by_username


def test_creates_normalized_player(db_session):
    username = f"test_{uuid4().hex}"

    player = get_or_create_player(
        db_session,
        " Chess.Com ",
        f" {username.upper()} ",
    )

    assert player.id is not None
    assert player.source == "chess.com"
    assert player.username == username
    assert player.created_at is not None

    stored_id = db_session.scalar(
        select(PlayerProfile.id).where(
            PlayerProfile.source == "chess.com",
            PlayerProfile.username == username,
        )
    )
    assert stored_id == player.id


def test_lookup_normalizes_source_and_username(db_session):
    username = f"lookup_{uuid4().hex}"
    stored = get_or_create_player(db_session, "chess.com", username)
    found = get_player_by_username(db_session, " Chess.Com ", f" {username.upper()} ")
    assert found is not None
    assert found.id == stored.id


def test_lookup_distinguishes_sources(db_session):
    username = f"lookup_{uuid4().hex}"
    first = get_or_create_player(db_session, "chess.com", username)
    second = get_or_create_player(db_session, "lichess", username)
    assert get_player_by_username(db_session, "chess.com", username).id == first.id
    assert get_player_by_username(db_session, "lichess", username).id == second.id


def test_missing_lookup_does_not_create_profile_or_commit(db_session, monkeypatch):
    username = f"missing_{uuid4().hex}"

    def unexpected_commit():
        raise AssertionError("Lookup must not commit")

    monkeypatch.setattr(db_session, "commit", unexpected_commit)
    assert get_player_by_username(db_session, "chess.com", username) is None
    assert db_session.scalar(select(func.count()).select_from(PlayerProfile).where(
        PlayerProfile.username == username,
    )) == 0


def test_repeated_calls_return_same_player(db_session):
    username = f"test_{uuid4().hex}"

    first = get_or_create_player(db_session, "chess.com", username)
    second = get_or_create_player(
        db_session, "CHESS.COM", username.upper()
    )

    assert first.id == second.id

    count = db_session.scalar(
        select(func.count())
        .select_from(PlayerProfile)
        .where(
            PlayerProfile.source == "chess.com",
            PlayerProfile.username == username,
        )
    )
    assert count == 1


def test_same_username_on_different_sources_creates_distinct_profiles(
    db_session,
):
    username = f"test_{uuid4().hex}"

    chesscom_player = get_or_create_player(
        db_session, "chess.com", username
    )
    lichess_player = get_or_create_player(
        db_session, "lichess", username
    )

    assert chesscom_player.id != lichess_player.id


def test_get_or_create_player_does_not_commit(db_session, monkeypatch):
    def unexpected_commit():
        raise AssertionError("The repository must leave commits to its caller")

    monkeypatch.setattr(db_session, "commit", unexpected_commit)

    username = f"test_{uuid4().hex}"
    player = get_or_create_player(db_session, "chess.com", username)

    assert player.username == username
