import httpx
import pytest

from backend.app.services.chesscom import (
    get_monthly_games,
    get_player_archives,
    get_recent_games,
)


@pytest.mark.parametrize(
    "archives",
    [[], ["https://api.chess.com/pub/player/hikaru/games/2026/01"]],
)
def test_archives_request_and_result(archives):
    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == "https://api.chess.com/pub/player/hikaru/games/archives"
        assert request.headers["User-Agent"] == "personalized-chess-ai/0.1.0"
        return httpx.Response(200, json={"archives": archives})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert get_player_archives(" Hikaru ", client=client) == archives
        assert not client.is_closed


@pytest.mark.parametrize("username", ["", "   ", "\n\t"])
def test_blank_username_is_rejected_before_request(username):
    def handler(request):
        pytest.fail("Invalid input must not make an HTTP request")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="username must not be blank"):
            get_player_archives(username, client=client)


@pytest.mark.parametrize("status", [404, 429, 500])
def test_http_errors_are_not_empty_archives(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError) as error:
            get_player_archives("hikaru", client=client)
    assert error.value.response.status_code == status


@pytest.mark.parametrize("payload", [{}, [], {"archives": None}, {"archives": [42]}])
def test_unexpected_response_shape(payload):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="archives.*list of strings"):
            get_player_archives("hikaru", client=client)


def test_timeout_propagates():
    def handler(request):
        raise httpx.ReadTimeout("Response timed out", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ReadTimeout):
            get_player_archives("hikaru", client=client)


def test_invalid_json_is_not_empty_archives():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="not JSON"))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError):
            get_player_archives("hikaru", client=client)


def test_monthly_games_request_and_result():
    games = [{"pgn": "example game text", "end_time": 1234567890}]

    def handler(request):
        assert request.method == "GET"
        assert str(request.url) == (
            "https://api.chess.com/pub/player/hikaru/games/2026/09"
        )

        return httpx.Response(200, json = {"games": games})

    with httpx.Client(transport = httpx.MockTransport(handler)) as client:
        result = get_monthly_games(" Hikaru ", 2026, 9, client = client)

        assert result == games
        assert not client.is_closed

@pytest.mark.parametrize("month", [0, 13])
def test_monthly_games_rejects_invalid_month(month):
    def handler(request):
        pytest.fail("Invalid month must not make an HTTP request")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="month must be between 1 and 12"):
            get_monthly_games("hikaru", 2026, month, client=client)

def test_monthly_games_returns_empty_list():
    games = []

    def handler(request):
        return httpx.Response(200, json = {"games": games})

    with httpx.Client(transport= httpx.MockTransport(handler)) as client:
        result = get_monthly_games("hikaru", 2026, 9, client = client)

        assert result == []

def test_monthly_games_rejects_missing_games():
    def handler(request):
        return httpx.Response(200, json = {})

    with httpx.Client(transport= httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="games"):
            get_monthly_games("hikaru", 2026, 9, client=client)


@pytest.mark.parametrize("status", [404, 429, 500])
def test_monthly_games_raises_on_http_error(status):

    def handler(request):
        return httpx.Response(status)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            get_monthly_games("hikaru", 2026, 9, client = client)
            
    
    
    


@pytest.mark.parametrize("count", [3, 2])
def test_recent_games_collects_across_months_and_stops(count):
    base = "https://api.chess.com/pub/player/hikaru/games"
    # Small timestamps make the ordering easy to see; no PGN parsing occurs.
    responses = {
        f"{base}/archives": {
            "archives": [f"{base}/2026/07", f"{base}/2026/08", f"{base}/2026/09"]
        },
        f"{base}/2026/09": {"games": [{"end_time": 300}, {"end_time": 400}]},
        f"{base}/2026/08": {"games": [{"end_time": 100}, {"end_time": 200}]},
    }
    requested_urls = []

    def handler(request):
        url = str(request.url)
        requested_urls.append(url)
        if url not in responses:
            pytest.fail(f"Unexpected request: {url}")
        return httpx.Response(200, json=responses[url])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = get_recent_games("hikaru", count, client=client)
        assert not client.is_closed

    assert result == [{"end_time": 400}, {"end_time": 300}, {"end_time": 200}][:count]
    expected_urls = [f"{base}/archives", f"{base}/2026/09"]
    if count == 3:
        expected_urls.append(f"{base}/2026/08")
    assert requested_urls == expected_urls


def test_recent_games_returns_fewer_when_archives_are_exhausted():
    base = "https://api.chess.com/pub/player/hikaru/games"
    responses = {
        f"{base}/archives": {"archives": [f"{base}/2025/12", f"{base}/2026/01"]},
        f"{base}/2026/01": {"games": []},
        f"{base}/2025/12": {"games": [{"end_time": 100}, {"end_time": 200}]},
    }
    requested_urls = []

    def handler(request):
        url = str(request.url)
        requested_urls.append(url)
        if url not in responses:
            pytest.fail(f"Unexpected request: {url}")
        return httpx.Response(200, json=responses[url])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = get_recent_games("hikaru", 5, client=client)

    assert result == [{"end_time": 200}, {"end_time": 100}]
    assert requested_urls == [f"{base}/archives", f"{base}/2026/01", f"{base}/2025/12"]


def test_recent_games_returns_empty_when_no_archives_exist():
    def handler(request):
        assert request.url.path == "/pub/player/hikaru/games/archives"
        return httpx.Response(200, json={"archives": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert get_recent_games("hikaru", 5, client=client) == []


def test_recent_games_zero_count_makes_no_request():
    def handler(request):
        pytest.fail("Zero count must not make an HTTP request")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert get_recent_games("hikaru", 0, client=client) == []


def test_recent_games_negative_count_is_rejected_before_request():
    def handler(request):
        pytest.fail("Negative count must not make an HTTP request")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="count must not be negative"):
            get_recent_games("hikaru", -1, client=client)


@pytest.mark.parametrize("failure", [429, "timeout"])
def test_recent_games_does_not_return_partial_results_on_failure(failure):
    base = "https://api.chess.com/pub/player/hikaru/games"

    def handler(request):
        url = str(request.url)
        if url == f"{base}/archives":
            return httpx.Response(200, json={
                "archives": [f"{base}/2026/08", f"{base}/2026/09"]
            })
        if url == f"{base}/2026/09":
            return httpx.Response(200, json={"games": [{"end_time": 300}]})
        if url == f"{base}/2026/08":
            if failure == "timeout":
                raise httpx.ReadTimeout("Response timed out", request=request)
            return httpx.Response(failure)
        pytest.fail(f"Unexpected request: {url}")

    expected_error = httpx.ReadTimeout if failure == "timeout" else httpx.HTTPStatusError
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(expected_error):
            get_recent_games("hikaru", 3, client=client)
        assert not client.is_closed
