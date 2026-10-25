# Timetable refactor simulation

## Purpose

Synthetic anonymous timetable HTML based on the existing caller URL and parser selectors. No provider mock
was searched or verified; this is a local regression fixture, not evidence of the live site's current markup.

## Execution

Run `postman simulation run postman/simulations/timetable.sim.yaml --port 4902 --output ndjson --no-history`.
Read the listening address, then set `$env:TIMETABLE_SIMULATION_URL='http://127.0.0.1:4902'` in PowerShell.
Run `.venv/Scripts/python.exe -m pytest -q tests/test_timetable_http_simulation.py` and stop the server with Ctrl+C.
The test changes the URL template only in its own process; the client makes real HTTP requests.

## Assumptions

- The fixture has one Monday lesson with code CS101. It models existing selectors and a GET URL containing
  the course ID; it cannot prove compatibility with the live site. (reasoned 2026-10-25, mock/default.js)
- Header routing requires `x-mock-slug: timetable`; the test supplies it. Status 500 must propagate as
  HTTPStatusError. (observed 2026-10-25)

## Observations

<!-- begin:observations -->
2026-10-25: the timetable member served GET /department-printer/123 with 200 and 500 before and after
the structural move. No members stayed silent; there is only one member. Live services were not exercised.
<!-- end:observations -->
