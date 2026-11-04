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

The completion toggle also runs in `test_eders_http_flow.py`. It checks both
`completed=true` and `completed=false` using fake credentials and the supplied
Moodle JSON contract. Success and failure evidence is recorded in `eders.context.yaml`.

On Windows, CLI 1.84.0 blocks the existing fixture's `require('fs')`. Run the
compatible version with `npm.cmd exec --yes --package=postman-cli@1.74.0 -- postman
simulation run postman/simulations/eders.sim.yaml`. Use the port printed at startup
for `MANASHELPER_EDERS_SIMULATION_PORT`; the verified run used port 3000.

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
