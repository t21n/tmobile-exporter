from pathlib import Path

import requests

from app import main

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "pass_telekom_home.html").read_text()
FIXTURE_HTML_NO_DAYS = (Path(__file__).parent / "fixtures" / "pass_telekom_home_no_days.html").read_text()
FIXTURE_HTML_UNLIMITED = (Path(__file__).parent / "fixtures" / "pass_telekom_home_unlimited.html").read_text()

EXPECTED_REMAINING = 12.34 * 1000 ** 3
EXPECTED_TOTAL = 50 * 1000 ** 3
EXPECTED_SECONDS = 5 * 86400 + 3 * 3600 + 20 * 60 + 10


def test_parse_usage_extracts_volume_and_countdown():
    usage = main.parse_usage(FIXTURE_HTML)

    assert usage is not None
    assert usage["remaining"] == EXPECTED_REMAINING
    assert usage["used"] == EXPECTED_TOTAL - EXPECTED_REMAINING
    assert usage["remaining_seconds"] == EXPECTED_SECONDS


def test_parse_usage_handles_missing_days_span():
    # Telekom omits the "days" span (rather than rendering "0 Tage") once
    # less than 24h remain in the billing cycle.
    usage = main.parse_usage(FIXTURE_HTML_NO_DAYS)

    assert usage is not None
    assert usage["remaining"] == 3.50 * 1000 ** 3
    assert usage["remaining_seconds"] == 18 * 3600 + 25 * 60 + 7


def test_parse_usage_handles_unlimited_pass():
    # When an unlimited data pass is active, Telekom shows "unbegrenzt"
    # instead of numbers and renders no countdown at all.
    usage = main.parse_usage(FIXTURE_HTML_UNLIMITED)

    assert usage == {"used": 0.0, "remaining": float("inf"), "remaining_seconds": 0}


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


def test_fetch_telekom_usage_sets_gauges_for_unlimited_pass(monkeypatch):
    class FakeResponse:
        text = FIXTURE_HTML_UNLIMITED

        def raise_for_status(self):
            pass

    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())

    main.fetch_telekom_usage()

    assert main.bytes_remaining._value.get() == float("inf")
    assert main.bytes_used._value.get() == 0.0
    assert main.days_remaining._value.get() == 0.0


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
