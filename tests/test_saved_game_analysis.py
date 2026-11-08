from contextlib import contextmanager
from types import SimpleNamespace

import chess.engine
import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.app.services import game_analysis as service


@pytest.fixture
def workflow(monkeypatch):
    state = SimpleNamespace(events=[], missing=False, fail=None,
                            read=object(), write=object(), result=object())

    class Factory:
        @contextmanager
        def __call__(self):
            state.events.append("read_open")
            try:
                yield state.read
            finally:
                state.events.append("read_close")

        @contextmanager
        def begin(self):
            state.events.append("write_open")
            try:
                yield state.write
                if state.fail == "commit":
                    raise SQLAlchemyError("Commit failed")
                state.events.append("commit")
            except Exception:
                state.events.append("rollback")
                raise
            finally:
                state.events.append("write_close")

    def lookup(session, game_id):
        assert session is state.read
        assert game_id == 7
        if state.fail == "lookup":
            raise SQLAlchemyError("Read failed")
        return None if state.missing else SimpleNamespace(pgn="1. e4 *")

    def analyze(pgn, *, engine_path, depth):
        assert state.events == ["read_open", "read_close"]
        assert (pgn, engine_path, depth) == ("1. e4 *", "test-stockfish", 12)
        state.events.append("analyze")
        if state.fail == "engine":
            raise chess.engine.EngineError("Search failed")
        return state.result

    def save(session, game_id, result):
        assert session is state.write
        assert game_id == 7
        assert result is state.result
        state.events.append("save")
        if state.fail == "save":
            raise SQLAlchemyError("Insert failed")
        return SimpleNamespace(id=42)

    monkeypatch.setattr(service, "get_game_by_id", lookup)
    monkeypatch.setattr(service, "analyze_game", analyze)
    monkeypatch.setattr(service, "create_game_analysis", save)
    state.factory = Factory()
    return state


def test_saved_analysis_closes_read_session_before_engine_and_commits_before_return(workflow):
    result = service.analyze_saved_game(7, session_factory=workflow.factory, engine_path="test-stockfish")
    assert result == 42
    assert workflow.events == ["read_open", "read_close", "analyze", "write_open", "save", "commit", "write_close"]


@pytest.mark.parametrize("field", ["game_id", "depth"])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "12", None])
def test_saved_analysis_rejects_invalid_arguments_before_database_access(workflow, field, value):
    arguments = dict(game_id=7, depth=12, session_factory=workflow.factory, engine_path="test-stockfish")
    arguments[field] = value
    with pytest.raises(ValueError, match=f"{field} must be a positive integer"):
        service.analyze_saved_game(**arguments)
    assert workflow.events == []


def test_saved_analysis_missing_game_skips_engine_and_write(workflow):
    workflow.missing = True
    with pytest.raises(service.GameNotFoundError):
        service.analyze_saved_game(7, session_factory=workflow.factory, engine_path="test-stockfish")
    assert workflow.events == ["read_open", "read_close"]


@pytest.mark.parametrize("stage, error_type, expected", [
    ("lookup", SQLAlchemyError, ["read_open", "read_close"]),
    ("engine", chess.engine.EngineError, ["read_open", "read_close", "analyze"]),
    ("save", SQLAlchemyError, ["read_open", "read_close", "analyze", "write_open", "save", "rollback", "write_close"]),
    ("commit", SQLAlchemyError, ["read_open", "read_close", "analyze", "write_open", "save", "rollback", "write_close"]),
])
def test_saved_analysis_propagates_failure_without_success(workflow, stage, error_type, expected):
    workflow.fail = stage
    with pytest.raises(error_type):
        service.analyze_saved_game(7, session_factory=workflow.factory, engine_path="test-stockfish")
    assert workflow.events == expected
