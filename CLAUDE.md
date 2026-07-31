# tmobile-exporter

Prometheus exporter that scrapes Deutsche Telekom / T-Mobile mobile data
usage (used/remaining volume, days left in the billing cycle) and exposes
it as gauges on `/metrics` (see [app/main.py](app/main.py)).

## The pass.telekom.de endpoint no longer returns JSON

Historically `pass.telekom.de` exposed a JSON REST API at
`/api/service/generic/v1/status` (`usedVolume`, `initialVolume`,
`remainingSeconds`). As of around July 2026, Telekom retired that API and
redesigned the site into a server-rendered HTML app (Jakarta Faces /
"Apollo" framework). The old path now returns a genuine `404` — this is
not a network or CI artifact, it was confirmed against a real T-Mobile
mobile connection.

The exporter now targets `https://pass.telekom.de/home`, which renders a
full HTML page with the usage figures embedded directly in the markup.
`app/main.py`'s `parse_usage()` extracts them via regex anchored on two
stable, unique elements observed in the rendered page:

- `<div class="data-pass-instance" id="summationPass">` — contains the
  aggregate remaining/total volume across all data passes:
  `remaining-volume-value`, `start-volume`, `volume-unit` (values use
  German decimal-comma formatting, e.g. `30,93`).
- The countdown spans `class="days"` / `"hours"` / `"mins"` / `"secs"` —
  time remaining in the current billing cycle (there was previously a
  single `remainingSeconds` field for this).

**The `days` span is conditionally omitted** once less than 24h remain in
the cycle — Telekom renders `18 Std. 25 Min. 07 Sek.` with no days markup
at all, rather than `0 Tage`. `parse_usage()` isolates the `<span
class="countdown">...</span>` block first (via `COUNTDOWN_BLOCK_PATTERN`)
and then looks up each unit independently within that block, defaulting
missing ones to `0` — this also avoids false hits from other unrelated
`class="days"` elements further down the page (e.g. purchasable data-pass
offer validity, "gültig für 31 Tage"). If a similar "hours"/"mins"/"secs"
omission ever shows up, extend the same per-unit lookup rather than
requiring all four in one sequential regex — that's what broke this the
first time (2026-07-31).

If Telekom changes the markup again, re-derive these anchors by fetching
`/home` from a device on the T-Mobile mobile network and grepping for
`volume-value` / `volume-bar` / `daysText` class names — that's how the
current anchors were found (no public docs exist for this).

## Why it only works on T-Mobile's mobile network

There's no visible auth token, cookie, or login on `/home` — it renders
the correct subscriber's data on a bare, unauthenticated request. This
strongly suggests carrier-side header enrichment (the mobile network
injects subscriber-identifying headers, a common zero-rating/captive
portal technique), not session-based auth. This is also why the endpoint
cannot be reached over WiFi or through a VPN/proxy — see
[README.md](README.md).

## Test structure

- **`test/test_unit.py`** — mocks `requests.get`, feeds parsing logic static
  HTML fixtures under `test/fixtures/` with synthetic (not real subscriber)
  numbers. Runs anywhere, no network needed. Covers `parse_usage()` directly
  (including the no-`days`-span case, `pass_telekom_home_no_days.html`)
  plus `fetch_telekom_usage()` error paths (HTTP errors, unexpected
  markup).
- **`test/test_e2e.py`** — the original real-network test; calls the live
  Telekom endpoint and asserts a gauge value `> 0`. Only meaningful when
  run from a host actually on T-Mobile mobile data.

## CI (`.github/workflows/build.yml`)

- `Build` job (matrix of OS/Python versions, no special network) now also
  installs `test/requirements.txt` and runs `pytest test/test_unit.py`.
- `End2End` job runs on the self-hosted `end2end` runner label, which is
  a host with a genuine T-Mobile mobile data connection, and runs
  `pytest test/test_e2e.py` against the live endpoint.
- Don't add the e2e test to the regular `Build` job matrix — those
  runners are GitHub-hosted and have no T-Mobile connectivity, so the
  live endpoint would 404/fail there regardless of whether the exporter
  code is correct.
