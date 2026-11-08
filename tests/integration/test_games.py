from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.models.game import Game
from backend.app.models.player import PlayerProfile
from backend.app.repositories.games import get_or_create_game, list_games_for_player
from backend.app.repositories.players import get_or_create_player


@pytest.fixture
def raw_game():
    token = uuid4().hex
    return {
        "url": f"https://www.chess.com/game/live/{token}",
        "white": {"username": f"white_{token}", "result": "win"},
        "black": {"username": f"black_{token}", "result": "resigned"},
        "time_class": "blitz",
        "rules": "chess",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }


@pytest.fixture
def player_game_history(db_session, raw_game):
    """Insert out of chronological order, with both colors and a timestamp tie."""
    username = raw_game["white"]["username"]
    games = {}
    for label, color, time_class, seconds in [
        ("newest", "white", "rapid", 30),
        ("oldest", "black", "blitz", 0),
        ("tie_first", "white", "blitz", 20),
        ("tie_second", "black", "blitz", 20),
        ("unrelated", None, "blitz", 40),
    ]:
        data = deepcopy(raw_game)
        data["url"] += f"-{label}"
        data["end_time"] += seconds
        data["time_class"] = time_class
        data["white"]["username"] = f"other_white_{uuid4().hex}"
        data["black"]["username"] = f"other_black_{uuid4().hex}"
        if color is not None:
            data[color]["username"] = username
        games[label] = get_or_create_game(db_session, data).id

    player = get_or_create_player(db_session, "chess.com", username)
    return player.id, games


def test_list_games_includes_both_colors_and_orders_by_time_then_id(
    db_session, player_game_history,
):
    player_id, games = player_game_history
    result = list_games_for_player(db_session, player_id)

    assert all(isinstance(game, Game) for game in result)
    assert [game.id for game in result] == [
        games["newest"], games["tie_second"], games["tie_first"], games["oldest"],
    ]


@pytest.mark.parametrize("time_class, labels", [
    ("blitz", ["tie_second", "tie_first", "oldest"]),
    ("rapid", ["newest"]),
    ("bullet", []),
])
def test_list_games_filters_time_class(
    db_session, player_game_history, time_class, labels,
):
    player_id, games = player_game_history
    result = list_games_for_player(db_session, player_id, time_class=time_class)
    assert [game.id for game in result] == [games[label] for label in labels]


@pytest.mark.parametrize("offset, labels", [
    (0, ["newest", "tie_second"]),
    (2, ["tie_first", "oldest"]),
    (3, ["oldest"]),
    (4, []),
    (10, []),
])
def test_list_games_paginates_ordered_results(
    db_session, player_game_history, offset, labels,
):
    player_id, games = player_game_history
    result = list_games_for_player(db_session, player_id, limit=2, offset=offset)
    assert [game.id for game in result] == [games[label] for label in labels]


def test_list_games_filters_before_paginating(db_session, player_game_history):
    player_id, games = player_game_history
    result = list_games_for_player(
        db_session, player_id, time_class="blitz", limit=1, offset=1,
    )
    assert [game.id for game in result] == [games["tie_first"]]


def test_list_games_returns_empty_for_player_without_games(
    db_session, player_game_history,
):
    player = get_or_create_player(db_session, "chess.com", f"empty_{uuid4().hex}")
    assert list_games_for_player(db_session, player.id) == []


def test_list_games_returns_empty_for_missing_player(db_session):
    player = get_or_create_player(db_session, "chess.com", f"deleted_{uuid4().hex}")
    player_id = player.id
    db_session.delete(player)
    db_session.flush()
    assert list_games_for_player(db_session, player_id) == []


def test_list_games_defaults_to_twenty_results(db_session, raw_game):
    game_ids = []
    for index in range(21):
        data = deepcopy(raw_game)
        data["url"] += f"-{index}"
        data["end_time"] += index
        stored = get_or_create_game(db_session, data)
        game_ids.append(stored.id)
    result = list_games_for_player(db_session, stored.white_player_id)
    assert [game.id for game in result] == list(reversed(game_ids))[:20]


def test_list_games_does_not_commit(db_session, player_game_history, monkeypatch):
    player_id, _ = player_game_history

    def unexpected_commit():
        pytest.fail("Listing games must not commit the caller's transaction")

    monkeypatch.setattr(db_session, "commit", unexpected_commit)
    assert len(list_games_for_player(db_session, player_id)) == 4


def test_stores_fields_and_player_links(db_session, raw_game):
    original = deepcopy(raw_game)
    stored = get_or_create_game(db_session, raw_game)
    stored_id = stored.id
    # Reload from PostgreSQL instead of relying on the session's object cache.
    db_session.expire_all()
    stored = db_session.get(Game, stored_id)

    assert stored is not None
    assert stored.source == "chess.com"
    assert stored.source_url == raw_game["url"]
    assert stored.white_result == "win"
    assert stored.black_result == "resigned"
    assert stored.time_class == "blitz"
    assert stored.rules == "chess"
    assert stored.pgn == raw_game["pgn"]
    assert stored.ended_at == datetime.fromtimestamp(raw_game["end_time"], tz=UTC)
    assert stored.ended_at.utcoffset() is not None
    assert stored.created_at is not None
    white = db_session.get(PlayerProfile, stored.white_player_id)
    black = db_session.get(PlayerProfile, stored.black_player_id)
    assert white.username == raw_game["white"]["username"]
    assert black.username == raw_game["black"]["username"]
    assert white.source == black.source == "chess.com"
    assert white.id != black.id
    assert raw_game == original


def test_reuses_existing_normalized_players(db_session, raw_game):
    white = get_or_create_player(db_session, "chess.com", raw_game["white"]["username"])
    black = get_or_create_player(db_session, "chess.com", raw_game["black"]["username"])
    raw_game["white"]["username"] = f" {white.username.upper()} "
    raw_game["black"]["username"] = black.username.upper()

    stored = get_or_create_game(db_session, raw_game)

    assert stored.white_player_id == white.id
    assert stored.black_player_id == black.id


def test_duplicate_import_preserves_existing_game(db_session, raw_game):
    first = get_or_create_game(db_session, raw_game)
    first_id = first.id
    changed = deepcopy(raw_game)
    changed["time_class"] = "rapid"
    second = get_or_create_game(db_session, changed)
    db_session.expire_all()

    assert second.id == first_id
    assert second.time_class == "blitz"
    assert db_session.scalar(
        select(func.count()).select_from(Game).where(
            Game.source == "chess.com", Game.source_url == raw_game["url"]
        )
    ) == 1
    assert db_session.scalar(
        select(func.count()).select_from(PlayerProfile).where(
            PlayerProfile.source == "chess.com",
            PlayerProfile.username.in_([
                raw_game["white"]["username"], raw_game["black"]["username"]
            ]),
        )
    ) == 2


def test_different_urls_create_distinct_games(db_session, raw_game):
    first = get_or_create_game(db_session, raw_game)
    other = deepcopy(raw_game)
    other["url"] += "-another"
    second = get_or_create_game(db_session, other)

    assert first.id != second.id
    assert first.white_player_id == second.white_player_id
    assert first.black_player_id == second.black_player_id


def test_repository_does_not_commit(db_session, monkeypatch, raw_game):
    def unexpected_commit():
        pytest.fail("Game repository must leave commits to its caller")

    monkeypatch.setattr(db_session, "commit", unexpected_commit)
    assert get_or_create_game(db_session, raw_game).id is not None


def test_caller_can_roll_back_game_and_new_players(db_session, raw_game):
    # A nested transaction lets us verify rollback within the fixture's transaction.
    transaction = db_session.begin_nested()
    stored = get_or_create_game(db_session, raw_game)
    game_id = stored.id
    player_ids = [stored.white_player_id, stored.black_player_id]
    transaction.rollback()

    assert db_session.scalar(select(Game.id).where(Game.id == game_id)) is None
    assert db_session.scalars(
        select(PlayerProfile.id).where(PlayerProfile.id.in_(player_ids))
    ).all() == []


@pytest.mark.parametrize("case, constraint", [
    ("same_player", "ck_games_different_players"),
    ("variant", "ck_games_standard_chess"),
])
def test_database_rejects_invalid_game_constraints(db_session, raw_game, case, constraint):
    if case == "same_player":
        raw_game["black"]["username"] = raw_game["white"]["username"]
    else:
        raw_game["rules"] = "chess960"

    # PostgreSQL aborts the savepoint on a constraint violation. Exiting the
    # nested context rolls it back, keeping the surrounding test session usable.
    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            get_or_create_game(db_session, raw_game)

    assert error.value.orig.diag.constraint_name == constraint


def test_database_rejects_missing_player_reference(db_session, raw_game):
    stored = get_or_create_game(db_session, raw_game)
    # Remove the referenced profile and try a new game pointing at its old ID.
    unused = get_or_create_player(db_session, "chess.com", f"unused_{uuid4().hex}")
    missing_id = unused.id
    db_session.delete(unused)
    db_session.flush()

    with pytest.raises(IntegrityError) as error:
        with db_session.begin_nested():
            db_session.add(Game(
                source="chess.com",
                source_url=raw_game["url"] + "-invalid",
                white_player_id=missing_id,
                black_player_id=stored.black_player_id,
                white_result="win", black_result="resigned",
                time_class="blitz", rules="chess",
                ended_at=stored.ended_at, pgn=raw_game["pgn"],
            ))
            db_session.flush()

    assert error.value.orig.diag.constraint_name == "fk_games_white_player_id_player_profiles"
