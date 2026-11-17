from types import SimpleNamespace

import pytest

from backend.app.services import practice


@pytest.fixture
def queue_source(monkeypatch):
    state = SimpleNamespace(session=object(), calls=[], analyses=[
        SimpleNamespace(id=i, game_id=100+i, engine_name="Test Engine", requested_depth=12)
        for i in range(1, 6)
    ])
    state.moves = [SimpleNamespace(game_analysis_id=run, ply=ply, color="white", fen_before="position")
                   for run, ply in [(1, 3), (1, 1), (2, 5), (3, 7), (4, 1)]]

    def analyses(session, player_id):
        assert session is state.session
        state.calls.append(player_id)
        return state.analyses

    def candidates(session, player_id, ids):
        assert session is state.session
        assert player_id == 7
        assert ids == [a.id for a in state.analyses]
        return state.moves

    monkeypatch.setattr(practice, "list_latest_player_analyses", analyses)
    monkeypatch.setattr(practice, "list_practice_candidates", candidates)
    return state


def test_queue_defaults_to_three_distinct_games_without_answers(queue_source):
    result = practice.build_practice_queue(queue_source.session, 7)
    assert result.analyzed_game_count == 5
    assert result.player_id == 7
    assert [p.game_id for p in result.positions] == [101, 102, 103]
    assert result.positions[0].model_dump() == dict(
        game_id=101, analysis_id=1, ply=3, color="white", fen="position",
        engine_name="Test Engine", requested_depth=12,
    )


@pytest.mark.parametrize("limit, count", [(1, 1), (10, 4)])
def test_queue_respects_limit_without_filling_duplicate_games(queue_source, limit, count):
    assert len(practice.build_practice_queue(queue_source.session, 7, limit=limit).positions) == count


def test_queue_counts_analyzed_games_with_no_candidates(queue_source):
    queue_source.moves = []
    result = practice.build_practice_queue(queue_source.session, 7)
    assert result.positions == []
    assert result.analyzed_game_count == 5


def test_queue_without_analyses(queue_source):
    queue_source.moves = []
    queue_source.analyses = []
    result = practice.build_practice_queue(queue_source.session, 7)
    assert result.positions == []
    assert result.analyzed_game_count == 0


@pytest.mark.parametrize("field, value", [
    (field, value) for field in ("player_id", "limit")
    for value in (0, -1, True, False, 1.5, "3", None)
] + [("limit", 11)])
def test_queue_validates_before_reading(queue_source, field, value):
    args = dict(player_id=7, limit=3)
    args[field] = value
    with pytest.raises(ValueError):
        practice.build_practice_queue(queue_source.session, **args)
    assert queue_source.calls == []
