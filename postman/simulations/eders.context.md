# Eders local flow

## Purpose

Run the existing fixture-based OBIS/Eders mock in `../mocks/eders/default.js` through
the real HTTP clients. Request shapes and fixture modes live in that handler and
`tests/modules/eders/test_eders_http_flow.py`.

## Execution

```sh
postman simulation run postman/simulations/eders.sim.yaml --port 4900 --output ndjson
# In another terminal, with the normal test database environment and migrations applied:
MANASHELPER_EDERS_SIMULATION_PORT=4900 .venv/bin/pytest -q tests/modules/eders/test_eders_http_flow.py
```

Wait for the `listening` event, inspect `request` events for the `eders` member,
and stop the simulation with Ctrl-C after the tests finish.

## Assumptions

- The simulation forwards sockets locally while retaining the clients' production
  URL, cookie and redirect handling. It proves fixture compatibility, not current
  university markup or authentication. (observed 2026-10-28)
- Database-backed tests need a dedicated migrated PostgreSQL database; existing
  development rows can affect assertions. (observed 2026-10-28)

## Observations

<!-- begin:observations -->
2026-10-28: the only member, `eders`, served OBIS login, SSO, profile, course
pagination and detail requests, plus the existing authentication/error scenarios,
with the test suite connected to PostgreSQL 18. No member stayed silent.
<!-- end:observations -->
