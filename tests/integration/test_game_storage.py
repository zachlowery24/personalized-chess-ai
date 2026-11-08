from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.models.game import Game
from backend.app.models.player import PlayerProfile
from backend.app.services.game_storage import save_imported_games


@pytest.fixture
def storage_batch(db_engine):
    """Use real commits, then remove only records allocated by this fixture."""
    factory = sessionmaker(bind=db_engine)
    games = []

    def make_game():
        token = uuid4().hex
        game = {
            "url": f"https://www.chess.com/game/live/{token}",
            "white": {"username": f"white_{token}", "result": "win"},
            "black": {"username": f"black_{token}", "result": "resigned"},
            "rules": "chess",
            "time_class": "blitz",
            "end_time": 1234567890,
            "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
        }
        games.append(game)
        return game

    try:
        yield factory, make_game
    finally:
        # Delete games before their referenced players. Unique names/URLs keep
        # cleanup confined to this test, including when an assertion fails.
        with factory.begin() as session:
            session.execute(delete(Game).where(
                Game.source == "chess.com",
                Game.source_url.in_([game["url"] for game in games]),
            ))
            names = [
                game[color]["username"]
                for game in games for color in ("white", "black")
            ]
            session.execute(delete(PlayerProfile).where(
                PlayerProfile.source == "chess.com",
                PlayerProfile.username.in_(names),
            ))


def test_saves_batch_and_commits_before_returning(storage_batch):
    factory, make_game = storage_batch
    games = [make_game(), make_game()]

    ids = save_imported_games(games, factory)

    assert len(ids) == 2
    assert ids[0] != ids[1]
    # A new session verifies that the transaction actually committed.
    with factory() as session:
        for game_id, original in zip(ids, games):
            stored = session.get(Game, game_id)
            assert stored is not None
            assert stored.source_url == original["url"]
            assert stored.pgn == original["pgn"]
            assert session.get(PlayerProfile, stored.white_player_id).username == original["white"]["username"]
            assert session.get(PlayerProfile, stored.black_player_id).username == original["black"]["username"]


def test_repeated_batches_return_existing_ids(storage_batch):
    factory, make_game = storage_batch
    games = [make_game(), make_game()]

    first_ids = save_imported_games(games, factory)
    second_ids = save_imported_games(games, factory)

    assert second_ids == first_ids
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Game).where(
            Game.source == "chess.com",
            Game.source_url.in_([game["url"] for game in games]),
        )) == 2


def test_duplicate_within_batch_returns_same_id(storage_batch):
    factory, make_game = storage_batch
    game = make_game()

    ids = save_imported_games([game, game], factory)

    assert len(ids) == 2
    assert ids[0] == ids[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Game).where(
            Game.source == "chess.com", Game.source_url == game["url"],
        )) == 1


def test_empty_batch_returns_empty_ids(storage_batch):
    factory, _ = storage_batch
    assert save_imported_games([], factory) == []


@pytest.mark.parametrize("failure", ["constraint", "missing_field"])
def test_later_failure_rolls_back_new_games_and_players(storage_batch, failure):
    factory, make_game = storage_batch
    first = make_game()
    invalid = make_game()
    if failure == "constraint":
        invalid["rules"] = "chess960"
        expected_error = IntegrityError
    else:
        # Repository expects validated data. This simulates a caller bug after
        # player insertion, verifying Python errors also roll back the batch.
        del invalid["pgn"]
        expected_error = KeyError

    with pytest.raises(expected_error):
        save_imported_games([first, invalid], factory)

    with factory() as session:
        assert session.scalars(select(Game.id).where(
            Game.source == "chess.com",
            Game.source_url.in_([first["url"], invalid["url"]]),
        )).all() == []
        names = [
            game[color]["username"]
            for game in (first, invalid) for color in ("white", "black")
        ]
        assert session.scalars(select(PlayerProfile.id).where(
            PlayerProfile.source == "chess.com",
            PlayerProfile.username.in_(names),
        )).all() == []

    # The factory remains usable after the failed transaction.
    assert len(save_imported_games([first], factory)) == 1


def test_failed_batch_preserves_previously_committed_game(storage_batch):
    factory, make_game = storage_batch
    existing = make_game()
    existing_id = save_imported_games([existing], factory)[0]
    new_game = make_game()
    invalid = make_game()
    invalid["rules"] = "chess960"

    with pytest.raises(IntegrityError):
        save_imported_games([existing, new_game, invalid], factory)

    with factory() as session:
        stored = session.get(Game, existing_id)
        assert stored is not None
        assert stored.pgn == existing["pgn"]
        assert session.get(PlayerProfile, stored.white_player_id) is not None
        assert session.get(PlayerProfile, stored.black_player_id) is not None
        assert session.scalars(select(Game.id).where(
            Game.source == "chess.com",
            Game.source_url.in_([new_game["url"], invalid["url"]]),
        )).all() == []


def test_import_workflow_persists_playable_games(monkeypatch, storage_batch):
    from backend.app.services import game_import

    factory, make_game = storage_batch
    playable = make_game()
    empty = make_game()
    empty["pgn"] = '[Event "Empty"]\n\n*'
    empty["white"] = dict(playable["white"])
    monkeypatch.setattr(game_import, "get_recent_games", lambda *args: [playable, empty])

    for _ in range(2):
        result = game_import.import_recent_games(
            playable["white"]["username"], 2, session_factory=factory
        )
        assert result["processed_count"] == 1
        assert result["skipped_count"] == 1
        with factory() as session:
            assert session.scalars(select(Game.source_url).where(
                Game.source_url.in_([playable["url"], empty["url"]])
            )).all() == [playable["url"]]
