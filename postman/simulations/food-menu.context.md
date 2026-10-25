# Food menu refactor simulation

## Purpose

Local synthetic HTML for the existing FoodMenuClient/FoodMenuParser contract. No university traffic or credentials.
The mock was built from the caller and parser selectors; no published provider mock was searched or verified.

## Execution

Run `postman simulation run postman/simulations/food-menu.sim.yaml --port 4901 --output ndjson --no-history`.
The listening event supplies the actual address. In PowerShell set
`$env:FOOD_MENU_SIMULATION_URL='http://127.0.0.1:4901'`, then run
`.venv/Scripts/python.exe -m pytest -q tests/modules/food_menu/test_food_menu_http_simulation.py`.
Stop the foreground simulation with Ctrl+C. The test changes only the module URL in its own process.

## Assumptions

- The selectors model current parser expectations, not a verified live university response. A pass cannot
  establish current live compatibility. (reasoned 2026-10-25, `postman/mocks/food-menu/default.js`)
- Header routing requires `x-mock-slug: food-menu`; tests supply it. The real HTTP client and parser run;
  responses with status 500 must raise HTTPStatusError. (observed 2026-10-25)

## Observations

<!-- begin:observations -->
2026-10-25: the food-menu member served GET /menu with 200 and 500 before and after the structural move.
No other members exist in this simulation; live services were not exercised.
<!-- end:observations -->
