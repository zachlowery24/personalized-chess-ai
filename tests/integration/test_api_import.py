from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from backend.app import main
from backend.app.models.game import Game
from backend.app.models.player import PlayerProfile
from backend.app.services import game_import


def test_api_import_commits_game_and_reuses_it_on_repeat(db_engine, monkeypatch):
    factory = sessionmaker(bind=db_engine)
    token = uuid4().hex
    white_name = f"white_{token}"
    black_name = f"black_{token}"
    source_url = f"https://www.chess.com/game/live/{token}"
    raw_game = {
        "url": source_url,
        "white": {"username": white_name, "result": "win"},
        "black": {"username": black_name, "result": "resigned"},
        "rules": "chess",
        "time_class": "blitz",
        "end_time": 1234567890,
        "pgn": '[Result "1-0"]\n\n1. e4 e5 1-0',
    }
    calls = []

    def fake_fetch(username, count):
        calls.append((username, count))
        return [raw_game]

    monkeypatch.setattr(game_import, "get_recent_games", fake_fetch)
    monkeypatch.setitem(
        main.app.dependency_overrides, main.get_session_factory, lambda: factory
    )

    try:
        saved_ids = None
        with TestClient(main.app) as client:
            for _ in range(2):
                response = client.post(
                    "/imports/chesscom",
                    json={"username": f" {white_name.upper()} ", "count": 1},
                )
                assert response.status_code == 200, response.text
                payload = response.json()
                assert payload["imported_count"] == 1
                assert payload["processed_count"] == 1
                assert payload["skipped_count"] == 0
                assert len(payload["games"]) == 1
                assert payload["games"][0]["source_url"] == source_url
                assert payload["games"][0]["user_color"] == "white"
                assert [move["uci"] for move in payload["games"][0]["moves"]] == [
                    "e2e4", "e7e5",
                ]

                # Independent session: rows must be committed before HTTP success.
                with factory() as session:
                    games = session.scalars(select(Game).where(
                        Game.source == "chess.com", Game.source_url == source_url
                    )).all()
                    assert len(games) == 1
                    stored = games[0]
                    players = session.scalars(select(PlayerProfile).where(
                        PlayerProfile.source == "chess.com",
                        PlayerProfile.username.in_([white_name, black_name]),
                    )).all()
                    assert len(players) == 2
                    by_name = {player.username: player for player in players}
                    assert stored.white_player_id == by_name[white_name].id
                    assert stored.black_player_id == by_name[black_name].id
                    assert stored.white_result == "win"
                    assert stored.black_result == "resigned"
                    assert stored.pgn == raw_game["pgn"]
                    current_ids = (
                        stored.id, stored.white_player_id, stored.black_player_id
                    )
                    if saved_ids is None:
                        saved_ids = current_ids
                    else:
                        assert current_ids == saved_ids
                    created_at = stored.created_at

                # GET uses its own session and the real repository/schema.
                retrieved = client.get(f"/games/{saved_ids[0]}")
                assert retrieved.status_code == 200, retrieved.text
                replay = client.get(f"/games/{saved_ids[0]}/moves")
                assert replay.status_code == 200, replay.text
                assert replay.json() == {
                    "game_id": saved_ids[0], "moves": payload["games"][0]["moves"],
                }
                saved_payload = retrieved.json()
                assert datetime.fromisoformat(saved_payload.pop("ended_at")) == (
                    datetime.fromtimestamp(raw_game["end_time"], tz=UTC)
                )
                assert datetime.fromisoformat(saved_payload.pop("created_at")) == created_at
                assert saved_payload == {
                    "id": saved_ids[0],
                    "source": "chess.com",
                    "source_url": source_url,
                    "white_player_id": saved_ids[1],
                    "black_player_id": saved_ids[2],
                    "white_result": "win",
                    "black_result": "resigned",
                    "time_class": "blitz",
                    "rules": "chess",
                    "pgn": raw_game["pgn"],
                }

            # Both participants can discover the committed game through the API.
            for player_id in saved_ids[1:]:
                username = white_name if player_id == saved_ids[1] else black_name
                profile = client.get("/players/lookup", params={
                    "username": f" {username.upper()} ",
                })
                assert profile.status_code == 200
                assert profile.json()["id"] == player_id
                assert profile.json()["username"] == username
                assert profile.json()["source"] == "chess.com"
                assert datetime.fromisoformat(profile.json()["created_at"]).tzinfo is not None
                listed = client.get(f"/players/{player_id}/games")
                assert listed.status_code == 200
                assert listed.json() == [retrieved.json()]
                filtered = client.get(
                    f"/players/{player_id}/games", params={"time_class": "rapid"}
                )
                assert filtered.status_code == 200
                assert filtered.json() == []
                next_page = client.get(
                    f"/players/{player_id}/games", params={"limit": 1, "offset": 1}
                )
                assert next_page.status_code == 200
                assert next_page.json() == []

            # Use a deleted test-owned ID rather than assuming an ID is unused.
            with factory.begin() as session:
                session.execute(delete(Game).where(Game.id == saved_ids[0]))
            missing = client.get(f"/games/{saved_ids[0]}")
            assert missing.status_code == 404
            assert missing.json() == {"detail": "Game not found."}

            empty = client.get(f"/players/{saved_ids[1]}/games")
            assert empty.status_code == 200
            assert empty.json() == []
            with factory.begin() as session:
                session.execute(delete(PlayerProfile).where(PlayerProfile.id == saved_ids[1]))
            unknown = client.get(f"/players/{saved_ids[1]}/games")
            assert unknown.status_code == 200
            assert unknown.json() == []
            missing_profile = client.get("/players/lookup", params={"username": white_name})
            assert missing_profile.status_code == 404
            assert missing_profile.json() == {"detail": "Player not found."}

        assert calls == [(white_name, 1), (white_name, 1)]
    finally:
        # Real commits need explicit cleanup, scoped to this test's unique data.
        with factory.begin() as session:
            session.execute(delete(Game).where(
                Game.source == "chess.com", Game.source_url == source_url
            ))
            session.execute(delete(PlayerProfile).where(
                PlayerProfile.source == "chess.com",
                PlayerProfile.username.in_([white_name, black_name]),
            ))
