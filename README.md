# Prometheus Exporter for T-Mobile

[![Docker Pulls](https://img.shields.io/docker/pulls/tools4homeautomation/tmobile-exporter)](https://hub.docker.com/r/tools4homeautomation/tmobile-exporter/)
[![Docker Stars](https://img.shields.io/docker/stars/tools4homeautomation/tmobile-exporter.svg)](https://hub.docker.com/r/tools4homeautomation/tmobile-exporter/)

No explicit authentication is needed for pass.telekom.de, but:

* The API only works when accessed over T-Mobile’s mobile network.
* The device must not be behind a VPN or proxy.
* If you're testing locally:
  * Disconnect from WiFi
  * Ensure mobile data is active
  * Run the script on a device with Python installed (e.g., Android w/ Termux, or a Raspberry Pi using a mobile dongle).

Metrics will look like this:
```
# HELP telekom_mobile_data_bytes_used Mobile data used (in bytes)
# TYPE telekom_mobile_data_bytes_used gauge
telekom_mobile_data_bytes_used 1234567890.0

# HELP telekom_mobile_data_bytes_remaining Mobile data remaining (in bytes)
# TYPE telekom_mobile_data_bytes_remaining gauge
telekom_mobile_data_bytes_remaining 987654321.0

# HELP telekom_mobile_days_remaining Days remaining in current billing cycle
# TYPE telekom_mobile_days_remaining gauge
telekom_mobile_days_remaining 8.2

```

Only works with host network: 
```
docker run --network host tools4homeautomation/tmobile-exporter:0.1.0
```

Use this scrape entry:
```
scrape_configs:
  - job_name: 'telekom'
    static_configs:
      - targets: ['<device-ip>:9877']
```
