import re
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

# The "summationPass" block holds the total remaining/initial volume across
# all data passes; the countdown span holds time left in the cycle.
VOLUME_PATTERN = re.compile(
    r'id="summationPass".*?'
    r'remaining-volume-value">\s*([\d.,]+)\s*<.*?'
    r'start-volume">\s*([\d.,]+)\s*<.*?'
    r'volume-unit">\s*(\w+)\s*<',
    re.DOTALL,
)
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


def parse_usage(html):
    """Extract usage figures from the pass.telekom.de "/home" page.

    Returns a dict with used/remaining bytes and remaining seconds in the
    current cycle, or None if the expected markup wasn't found.
    """
    volume_match = VOLUME_PATTERN.search(html)
    countdown_block_match = COUNTDOWN_BLOCK_PATTERN.search(html)
    if not volume_match or not countdown_block_match:
        return None

    remaining_str, total_str, unit = volume_match.groups()
    multiplier = UNIT_MULTIPLIERS.get(unit.upper())
    if multiplier is None:
        return None

    remaining = _parse_german_number(remaining_str) * multiplier
    total = _parse_german_number(total_str) * multiplier

    countdown_block = countdown_block_match.group(1)
    countdown_matches = {name: pattern.search(countdown_block) for name, pattern in COUNTDOWN_UNIT_PATTERNS.items()}
    if not any(countdown_matches.values()):
        return None
    units = {name: int(match.group(1)) if match else 0 for name, match in countdown_matches.items()}
    days, hours, mins, secs = units["days"], units["hours"], units["mins"], units["secs"]

    return {
        "used": total - remaining,
        "remaining": remaining,
        "remaining_seconds": days * 86400 + hours * 3600 + mins * 60 + secs,
    }


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
