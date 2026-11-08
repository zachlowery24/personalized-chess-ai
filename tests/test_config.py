import pytest
from pydantic import ValidationError

from backend.app.config import Settings


@pytest.fixture
def database_env(monkeypatch):
    values = {
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_chess",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test@password",
    }

    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_builds_database_url(database_env):
    settings = Settings(_env_file=None)
    url = settings.database_url

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "127.0.0.1"
    assert url.port == 5432
    assert url.database == "test_chess"
    assert url.username == "test_user"
    assert url.password == "test@password"
    assert "test@password" not in url.render_as_string(hide_password=True)


@pytest.mark.parametrize("port", ["0", "65536", "not-a-number"])
def test_settings_rejects_invalid_port(database_env, monkeypatch, port):
    monkeypatch.setenv("POSTGRES_PORT", port)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert error.value.errors()[0]["loc"] == ("postgres_port",)


def test_settings_requires_password(database_env, monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert error.value.errors()[0]["loc"] == ("postgres_password",)