import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from prometheus_client import Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

# Create Prometheus metrics
registry = CollectorRegistry()
bytes_used = Gauge('telekom_mobile_data_bytes_used', 'Mobile data used (in bytes)', registry=registry)
bytes_remaining = Gauge('telekom_mobile_data_bytes_remaining', 'Mobile data remaining (in bytes)', registry=registry)
days_remaining = Gauge('telekom_mobile_days_remaining', 'Days remaining in current billing cycle', registry=registry)

# Telekom retired the JSON API in favor of a server-rendered usage page.
# The figures we need are embedded in the HTML of this page instead.
API_URL = "https://pass.telekom.de/home"

UNIT_MULTIPLIERS = {"KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3, "TB": 1000 ** 4}

# Sentinel for "remaining" when an unlimited data pass is active. A real
# IEEE Infinity (float('inf')) round-trips fine through the exporter itself,
# but Prometheus's query engine turns any arithmetic on +Inf (differences,
# ratios, rate()) into NaN, which then commonly renders as 0 — confirmed
# 2026-08-29 against a live Prometheus instance. A large finite value behaves
# like normal data through PromQL instead.
UNLIMITED_REMAINING_BYTES = sys.float_info.max

# The "summationPass" block holds the total remaining/initial volume across
# all data passes; the countdown span holds time left in the cycle.
VOLUME_PATTERN = re.compile(
    r'id="summationPass".*?'
    r'remaining-volume-value">\s*([\d.,]+)\s*<.*?'
    r'start-volume">\s*([\d.,]+)\s*<.*?'
    r'volume-unit">\s*(\w+)\s*<',
    re.DOTALL,
)
# When an unlimited data pass is active, Telekom replaces the numeric
# breakdown above with a plain "unbegrenzt" label and renders no countdown
# at all (there's nothing to count down to) — see CLAUDE.md.
UNLIMITED_PATTERN = re.compile(r'id="summationPass".*?<span class="volume">\s*unbegrenzt\s*</span>', re.DOTALL)
# Isolate the countdown span first: "days" is a class name used elsewhere on
# the page too (e.g. data pass offer validity), so matching it globally would
# risk picking up an unrelated number. Within the isolated block, "days" is
# itself optional — Telekom omits it once under 24h remain in the cycle.
COUNTDOWN_BLOCK_PATTERN = re.compile(r'class="countdown">(.*?)</div>', re.DOTALL)
COUNTDOWN_UNIT_PATTERNS = {
    "days": re.compile(r'class="days">(\d+)</span>'),
    "hours": re.compile(r'class="hours">(\d+)</span>'),
    "mins": re.compile(r'class="mins">(\d+)</span>'),
    "secs": re.compile(r'class="secs">(\d+)</span>'),
}


def _parse_german_number(value):
    return float(value.strip().replace(".", "").replace(",", "."))


def _extract_remaining_seconds(html):
    """Read the days/hours/mins/secs countdown, or None if it's missing."""
    countdown_block_match = COUNTDOWN_BLOCK_PATTERN.search(html)
    if not countdown_block_match:
        return None

    countdown_block = countdown_block_match.group(1)
    countdown_matches = {name: pattern.search(countdown_block) for name, pattern in COUNTDOWN_UNIT_PATTERNS.items()}
    if not any(countdown_matches.values()):
        return None
    units = {name: int(match.group(1)) if match else 0 for name, match in countdown_matches.items()}
    return units["days"] * 86400 + units["hours"] * 3600 + units["mins"] * 60 + units["secs"]


def parse_usage(html):
    """Extract usage figures from the pass.telekom.de "/home" page.

    Returns a dict with used/remaining bytes and remaining seconds in the
    current cycle, or None if the expected markup wasn't found. When an
    unlimited data pass is active, "remaining" is UNLIMITED_REMAINING_BYTES
    and "used"/"remaining_seconds" are 0 — the page gives no numbers for
    either.
    """
    volume_match = VOLUME_PATTERN.search(html)
    if volume_match:
        remaining_str, total_str, unit = volume_match.groups()
        multiplier = UNIT_MULTIPLIERS.get(unit.upper())
        if multiplier is None:
            return None

        remaining_seconds = _extract_remaining_seconds(html)
        if remaining_seconds is None:
            return None

        remaining = _parse_german_number(remaining_str) * multiplier
        total = _parse_german_number(total_str) * multiplier
        return {
            "used": total - remaining,
            "remaining": remaining,
            "remaining_seconds": remaining_seconds,
        }

    if UNLIMITED_PATTERN.search(html):
        return {"used": 0.0, "remaining": UNLIMITED_REMAINING_BYTES, "remaining_seconds": 0}

    return None


def fetch_telekom_usage():
    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()

        usage = parse_usage(response.text)
        if usage is None:
            print("Unexpected data format from Telekom — are you on T-Mobile mobile data?")
            return

        bytes_used.set(usage["used"])
        bytes_remaining.set(usage["remaining"])
        days_remaining.set(usage["remaining_seconds"] / (60 * 60 * 24))  # convert to days
    except Exception as e:
        print(f"Error fetching Telekom usage: {e}")

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            fetch_telekom_usage()
            metrics_data = generate_latest(registry)
            self.send_response(200)
            self.send_header('Content-type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(metrics_data)
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    PORT = 9877
    print(f"Starting Telekom Prometheus Exporter on port {PORT}")
    server = HTTPServer(('', PORT), MetricsHandler)
    server.serve_forever()
