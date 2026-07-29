from pathlib import Path

import requests

from app import main

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "pass_telekom_home.html").read_text()

EXPECTED_REMAINING = 12.34 * 1000 ** 3
EXPECTED_TOTAL = 50 * 1000 ** 3
EXPECTED_SECONDS = 5 * 86400 + 3 * 3600 + 20 * 60 + 10


def test_parse_usage_extracts_volume_and_countdown():
    usage = main.parse_usage(FIXTURE_HTML)

    assert usage is not None
    assert usage["remaining"] == EXPECTED_REMAINING
    assert usage["used"] == EXPECTED_TOTAL - EXPECTED_REMAINING
    assert usage["remaining_seconds"] == EXPECTED_SECONDS


def test_parse_usage_returns_none_for_unexpected_markup():
    assert main.parse_usage("<html><body>not a data usage page</body></html>") is None


def test_fetch_telekom_usage_sets_gauges(monkeypatch):
    class FakeResponse:
        text = FIXTURE_HTML

        def raise_for_status(self):
            pass

    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())

    main.fetch_telekom_usage()

    assert main.bytes_remaining._value.get() == EXPECTED_REMAINING
    assert main.bytes_used._value.get() == EXPECTED_TOTAL - EXPECTED_REMAINING
    assert main.days_remaining._value.get() == EXPECTED_SECONDS / 86400


def test_fetch_telekom_usage_handles_http_error(monkeypatch, capsys):
    class FailingResponse:
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("404 Client Error")

    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FailingResponse())

    main.fetch_telekom_usage()

    assert "Error fetching Telekom usage" in capsys.readouterr().out


def test_fetch_telekom_usage_handles_unexpected_markup(monkeypatch, capsys):
    class FakeResponse:
        text = "<html><body>not a data usage page</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())

    main.fetch_telekom_usage()

    assert "Unexpected data format from Telekom" in capsys.readouterr().out
