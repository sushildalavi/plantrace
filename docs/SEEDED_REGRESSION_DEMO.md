# Seeded Regression Demo

## Demo flow

1. Query uses an index.
2. Index is removed or the plan changes.
3. Sequential scan is detected.
4. Dashboard or API flags the regression.
5. Query detail shows deterministic recommendations for the latest snapshot.

## Notes

- This should be deterministic and fixture-backed.
- Rule-based suggestions should be labeled as such.
