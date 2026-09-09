"""System evals for the demo (ADR 0006).

Run them against a live backend with ``python -m evals.run --base-url http://localhost:8000``.
Every number they produce is observed from real requests; ``evals/results/latest.json`` is the
committed artifact the UI and README point at.
"""

SCHEMA_VERSION = 1
