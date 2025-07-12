import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from prometheus_client import Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

# Create Prometheus metrics
registry = CollectorRegistry()
bytes_used = Gauge('telekom_mobile_data_bytes_used', 'Mobile data used (in bytes)', registry=registry)
bytes_remaining = Gauge('telekom_mobile_data_bytes_remaining', 'Mobile data remaining (in bytes)', registry=registry)
days_remaining = Gauge('telekom_mobile_days_remaining', 'Days remaining in current billing cycle', registry=registry)

API_URL = "http://pass.telekom.de/api/service/generic/v1/status"

def fetch_telekom_usage():
    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("usedBytes") is not None:
            bytes_used.set(data["usedBytes"])
            bytes_remaining.set(data["remainingBytes"])
            days_remaining.set(data["remainingSeconds"] / (60 * 60 * 24))  # convert to days
        else:
            print("Unexpected data format from Telekom")
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
