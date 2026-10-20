# Held-out cases

These cases measure the guards on commands nobody tuned them against. `tools/bench.py` reports them apart from the main corpus, and they are the numbers to quote.

The rules:

- Write a case from what the README says a guard stops, not from the guard's code. Give it a `source` that says who wrote it and how.
- Commit new cases before you run them, so the history shows they weren't changed to fit the result.
- Don't add `known_miss` or `limit`. A held-out case records what should happen, and the guard either matches it or it doesn't.
- Don't change a guard to pass a held-out case in the same change that adds the case. Open an issue instead.
- Once a guard is changed to fix a held-out case, the guard has been tuned against it. Move the case into the main corpus, and add new held-out cases to replace it.

`guards.test.py` checks that these files parse, but does not fail on their results.
